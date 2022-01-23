from time import time
import os, sys
import tensorflow as tf
import numpy as np
import logging
import argparse
from time import time

import tensorflow as tf
import os
import shutil

import tensorflow_text as text # text should be imported!

MODEL = None
IMDB_DATASET = '/dataset/imdb/'
# https://www.tensorflow.org/text/tutorials/classify_text_with_bert
# talking-heads_base
# tfhub_handle_encoder = 'https://tfhub.dev/tensorflow/talkheads_ggelu_bert_en_base/1'
# tfhub_handle_preprocess = 'https://tfhub.dev/tensorflow/bert_en_uncased_preprocess/3'

sys.path.insert(0, '/papi')
from datetime import datetime
from papi_helper import pypapi_wrapper
EVENTSET = int(os.environ.get('EVENTSET'))
NUM = os.environ.get('NUM')
TIMESTAMP = datetime.today().strftime('%Y-%m-%d-%H:%M:%S.%f')

def configs():
    logging.basicConfig(level=logging.DEBUG, \
                        format='[%(asctime)s, %(lineno)d %(funcName)s | TalkingHeads] %(message)s')
    parser = argparse.ArgumentParser()
    parsed_args = parser.parse_args()

    import subprocess, psutil
    cpu_sockets =  int(subprocess.check_output('cat /proc/cpuinfo | grep "physical id" | sort -u | wc -l', shell=True))
    phy_cores = int(psutil.cpu_count(logical=False)/cpu_sockets)
    # print(cpu_sockets, phy_cores)

    tf.config.threading.set_inter_op_parallelism_threads(cpu_sockets) # num of sockets: 2
    tf.config.threading.set_intra_op_parallelism_threads(phy_cores) # num of phy cores: 12
    os.environ['OMP_NUM_THREADS'] = str(phy_cores)
    os.environ['KMP_AFFINITY'] = 'granularity=fine,verbose,compact,1,0'

def print_my_examples(inputs, results):
    result_for_printing = [f'input: {inputs[i]:<30} : score: {results[i][0]:.6f}'
                                for i in range(len(inputs))]
    print(*result_for_printing, sep='\n')
    print()

if __name__ == '__main__':
    configs()

    dataset_name = 'imdb-bert_expert'
    saved_model_path = '/models/imdb_prediction/{}_bert'.format(dataset_name.replace('/', '_'))

    # classifier_model.save(saved_model_path, include_optimizer=False)
    s = time()
    reloaded_model = tf.saved_model.load(saved_model_path)
    e = time()

    examples = [
        'this is such an amazing movie!',  # this is the same sentence tried earlier
        'The movie was great!',
        'The movie was meh.',
        'The movie was okish.',
        'The movie was terrible...'
    ]

    # t1 = time()
    # reloaded_results = tf.sigmoid(reloaded_model(tf.constant(examples)))
    # t2 = time()
    # # print(t2-t1)
    # # print_my_examples(examples, reloaded_results)

    # t1 = time()
    # reloaded_results = tf.sigmoid(reloaded_model(tf.constant(examples)))
    # t2 = time()
    # # print(t2-t1)
    # # original_results = tf.sigmoid(classifier_model(tf.constant(examples)))
    # # print_my_examples(examples, reloaded_results)

    # t1 = time()
    # reloaded_results = tf.sigmoid(reloaded_model(tf.constant(['it is an awesome movie!'])))
    # t2 = time()
    # # print(t2-t1)

    # https://www.rogerebert.com/reviews/great-movie-psycho-1960
    with open('psycho.txt') as f:
        roger_ebert_hitchcock_psycho = f.readlines()
    s = time()
    papi = pypapi_wrapper(EVENTSET)
    papi.start()
    reloaded_results = tf.sigmoid(reloaded_model(tf.constant(roger_ebert_hitchcock_psycho)))
    papi.stop()
    results = papi.read()
    os.makedirs(f'/data/mon/{NUM}', exist_ok=True)
    with open(f'/data/mon/{NUM}/event-{TIMESTAMP}-{EVENTSET}.log', 'a') as f:

        print(','.join([str(result) for result in results]))
        f.write(','.join([str(result) for result in results]) + '\n')
        papi.cleanup()
    e = time()
    # print(t2-t1)
    logging.info(f'inference_time={e-s}')
    # print_my_examples(roger_ebert_hitchcock_psycho, reloaded_results)
    # original_results = tf.sigmoid(classifier_model(tf.constant(examples)))

    # print('Results from the saved model:')
