from time import time
import os, sys
import tensorflow as tf
import numpy as np
import logging
import argparse

import tensorflow as tf
import os
import shutil

import tensorflow_hub as hub
import tensorflow_text as text
from official.nlp import optimization  # to create AdamW optimizer

MODEL = None
IMDB_DATASET = '/dataset/imdb/'
# https://www.tensorflow.org/text/tutorials/classify_text_with_bert
# small_bert/bert_en_uncased_L-4_H-512_A-8
tfhub_handle_encoder = 'https://tfhub.dev/tensorflow/small_bert/bert_en_uncased_L-4_H-512_A-8/1'
tfhub_handle_preprocess = 'https://tfhub.dev/tensorflow/bert_en_uncased_preprocess/3'

def configs():
    logging.basicConfig(level=logging.DEBUG, \
                        format='[%(asctime)s, %(lineno)d %(funcName)s | BERT_Expert] %(message)s')
    parser = argparse.ArgumentParser()
    parsed_args = parser.parse_args()

    import subprocess, psutil
    cpu_sockets =  int(subprocess.check_output('cat /proc/cpuinfo | grep "physical id" | sort -u | wc -l', shell=True))
    phy_cores = int(psutil.cpu_count(logical=False)/cpu_sockets)
    print(cpu_sockets, phy_cores)

    tf.config.threading.set_inter_op_parallelism_threads(cpu_sockets) # num of sockets: 2
    tf.config.threading.set_intra_op_parallelism_threads(phy_cores) # num of phy cores: 12
    os.environ['OMP_NUM_THREADS'] = str(phy_cores)
    os.environ['KMP_AFFINITY'] = 'granularity=fine,verbose,compact,1,0'

def build_classifier_model():
    text_input = tf.keras.layers.Input(shape=(), dtype=tf.string, name='text')
    preprocessing_layer = hub.KerasLayer(tfhub_handle_preprocess, name='preprocessing')
    encoder_inputs = preprocessing_layer(text_input)
    encoder = hub.KerasLayer(tfhub_handle_encoder, trainable=True, name='BERT_encoder')
    outputs = encoder(encoder_inputs)
    net = outputs['pooled_output']
    net = tf.keras.layers.Dropout(0.1)(net)
    net = tf.keras.layers.Dense(1, activation=None, name='classifier')(net)
    return tf.keras.Model(text_input, net)

def print_my_examples(inputs, results):
    result_for_printing = [f'input: {inputs[i]:<30} : score: {results[i][0]:.6f}'
                                for i in range(len(inputs))]
    print(*result_for_printing, sep='\n')
    print()

if __name__ == '__main__':
    configs()
    # load_classes()

    os.chdir(IMDB_DATASET)
    dataset_dir = os.path.join(IMDB_DATASET, 'aclImdb')

    train_dir = os.path.join(dataset_dir, 'train')

    # remove unused folders to make it easier to load the data
    remove_dir = os.path.join(train_dir, 'unsup')
    shutil.rmtree(remove_dir)

    try:
        AUTOTUNE = tf.data.AUTOTUNE
    except:
        AUTOTUNE = tf.data.experimental.AUTOTUNE
    batch_size = 32
    seed = 42

    raw_train_ds = tf.keras.utils.text_dataset_from_directory(
        'aclImdb/train',
        batch_size=batch_size,
        validation_split=0.2,
        subset='training',
        seed=seed)

    class_names = raw_train_ds.class_names
    train_ds = raw_train_ds.cache().prefetch(buffer_size=AUTOTUNE)

    val_ds = tf.keras.utils.text_dataset_from_directory(
        'aclImdb/train',
        batch_size=batch_size,
        validation_split=0.2,
        subset='validation',
        seed=seed)

    val_ds = val_ds.cache().prefetch(buffer_size=AUTOTUNE)

    test_ds = tf.keras.utils.text_dataset_from_directory(
        'aclImdb/test',
        batch_size=batch_size)

    test_ds = test_ds.cache().prefetch(buffer_size=AUTOTUNE)

    for text_batch, label_batch in train_ds.take(1):
        for i in range(3):
            print(f'Review: {text_batch.numpy()[i]}')
            label = label_batch.numpy()[i]
            print(f'Label : {label} ({class_names[label]})')

    bert_preprocess_model = hub.KerasLayer(tfhub_handle_preprocess)

    text_test = ['this is such an amazing movie!']
    text_preprocessed = bert_preprocess_model(text_test)

    print(f'Keys       : {list(text_preprocessed.keys())}')
    print(f'Shape      : {text_preprocessed["input_word_ids"].shape}')
    print(f'Word Ids   : {text_preprocessed["input_word_ids"][0, :12]}')
    print(f'Input Mask : {text_preprocessed["input_mask"][0, :12]}')
    print(f'Type Ids   : {text_preprocessed["input_type_ids"][0, :12]}')

    bert_model = hub.KerasLayer(tfhub_handle_encoder)

    bert_results = bert_model(text_preprocessed)

    print(f'Loaded BERT: {tfhub_handle_encoder}')
    print(f'Pooled Outputs Shape:{bert_results["pooled_output"].shape}')
    print(f'Pooled Outputs Values:{bert_results["pooled_output"][0, :12]}')
    print(f'Sequence Outputs Shape:{bert_results["sequence_output"].shape}')
    print(f'Sequence Outputs Values:{bert_results["sequence_output"][0, :12]}')

    classifier_model = build_classifier_model()
    bert_raw_result = classifier_model(tf.constant(text_test))
    print(tf.sigmoid(bert_raw_result))

    # tf.keras.utils.plot_model(classifier_model)

    loss = tf.keras.losses.BinaryCrossentropy(from_logits=True)
    metrics = tf.metrics.BinaryAccuracy()

    epochs = 5
    steps_per_epoch = tf.data.experimental.cardinality(train_ds).numpy()
    num_train_steps = steps_per_epoch * epochs
    num_warmup_steps = int(0.1*num_train_steps)

    init_lr = 3e-5
    optimizer = optimization.create_optimizer(init_lr=init_lr,
                                            num_train_steps=num_train_steps,
                                            num_warmup_steps=num_warmup_steps,
                                            optimizer_type='adamw')

    classifier_model.compile(optimizer=optimizer, loss=loss,  metrics=metrics)

    print(f'Training model with {tfhub_handle_encoder}')
    history = classifier_model.fit(x=train_ds,
                                validation_data=val_ds,
                                epochs=epochs)

    loss, accuracy = classifier_model.evaluate(test_ds)

    print(f'Loss: {loss}')
    print(f'Accuracy: {accuracy}')

    dataset_name = 'imdb-small_bert'
    saved_model_path = '/models/imdb_prediction/{}_bert'.format(dataset_name.replace('/', '_'))

    classifier_model.save(saved_model_path, include_optimizer=False)
    reloaded_model = tf.saved_model.load(saved_model_path)

    examples = [
        'this is such an amazing movie! this is such an amazing movie! this is such an amazing movie! this is such an amazing movie! this is such an amazing movie!',  # this is the same sentence tried earlier
        'The movie was great!',
        'The movie was meh.',
        'The movie was okish.',
        'The movie was terrible...'
    ]

    reloaded_results = tf.sigmoid(reloaded_model(tf.constant(examples)))
    original_results = tf.sigmoid(classifier_model(tf.constant(examples)))

    print('Results from the saved model:')
    print_my_examples(examples, reloaded_results)
    print('Results from the model in memory:')
    print_my_examples(examples, original_results)


    # s = time()
    # build_model()
    # e = time()
    # logging.info(f'graph_construction_time={e-s}')
    # # image = resize_image(IMG_FILE)
    # s = time()
    # result = MODEL(image)
    # e = time()
    # logging.info(f'inference_time={e-s}')
    # cls = np.argmax(result)
    # # logging.info(f'{CLASSES[cls]}')
