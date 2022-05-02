# https://gist.github.com/yrevar/942d3a0ac09ec9e5eb3a
# imagenet index label
import os, sys
# import tensorflow as tf
import numpy as np
import logging
import argparse
sys.path.insert(0, '/root/')
sys.path.insert(0, '/root/tfrpc/client')
from pocket_tf_if import TFDataType
from yolo_msgq import PocketMessageChannel

from time import time


# https://github.com/tensorflow/hub/blob/master/examples/colab/tf2_object_detection.ipynb
CUR_DIR = os.path.dirname(os.path.realpath(__file__))
COCO_DIR = '/root/coco2017'
# IMG_FILE = '000000581206.jpg' # Hot dogs
# IMG_FILE = '000000578967.jpg' # Train
# IMG_FILE = '000000093965.jpg' # zebra
# IMG_FILE = '000000104424.jpg' # a woman with a tennis racket
IMG_FILE = '000000292446.jpg' # pizza
CLASS_LABLES_FILE = 'imagenet1000_clsidx_to_labels.txt'
CLASSES = {}
MODEL: TFDataType.Model
msgq = PocketMessageChannel.get_instance()

def configs():
    global IMG_FILE
    logging.basicConfig(level=logging.DEBUG, \
                        format='[%(asctime)s, %(lineno)d %(funcName)s | SmallBERT] %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', default=IMG_FILE)
    parsed_args = parser.parse_args()
    IMG_FILE = parsed_args.image

def print_my_examples(inputs, results):
    result_for_printing = [f'input: {inputs[i]:<30} : score: {results[i][0]:.6f}'
                                for i in range(len(inputs))]
    print(*result_for_printing, sep='\n')
    print()

if __name__ == '__main__':
    configs()
    model_name = 'imdb-small_bert'
    s = time()
    reloaded_model = msgq.tf_saved__model_load(model_name)
    e = time()
    logging.info(f'graph_construction_time={e-s}')

    
    examples = [
        'this is such an amazing movie!',  # this is the same sentence tried earlier
        'The movie was great!',
        'The movie was meh.',
        'The movie was okish.',
        'The movie was terrible...'
    ]

    # constant = msgq.tf_constant(examples)
    # result = reloaded_model(constant)
    # result = msgq.tf_sigmoid(result)
    # print(result)

    # exit()
    # t1 = time()
    # reloaded_results = msgq.tf_sigmoid(reloaded_model(msgq.tf_constant(examples)))
    # t2 = time()
    # # print(t2-t1)
    # # print_my_examples(examples, reloaded_results)

    # t1 = time()
    # reloaded_results = msgq.tf_sigmoid(reloaded_model(msgq.tf_constant(examples)))
    # t2 = time()
    # # print(t2-t1)
    # # original_results = tf.sigmoid(classifier_model(tf.constant(examples)))
    # # print_my_examples(examples, reloaded_results)

    # t1 = time()
    # reloaded_results = msgq.tf_sigmoid(reloaded_model(msgq.tf_constant(['it is an awesome movie!'])))
    # t2 = time()
    # # print(t2-t1)

    # https://www.rogerebert.com/reviews/great-movie-psycho-1960

    import cProfile, pstats, io
    pr = cProfile.Profile()
    pr.enable()

    with open('psycho.txt') as f:
        roger_ebert_hitchcock_psycho = f.readlines()
    reloaded_results = msgq.tf_sigmoid(reloaded_model(msgq.tf_constant(roger_ebert_hitchcock_psycho)))

    pr.disable()
    s = io.StringIO()
    sortby = 'cumulative'
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats()

    lines = s.getvalue().split('\n')
    lines = list((filter(lambda l: 'seconds' in l, lines))) + \
            list((filter(lambda l: 'receive' in l, lines))) + \
            list((filter(lambda l: 'send' in l, lines)))
    lines = [line.strip().split() for line in lines]
    total_time = float(lines[0][-2])
    be_time = float(lines[1][1]) + float(lines[2][1])
    fe_time = total_time - be_time

    logging.info(f'total_time={total_time}')
    logging.info(f'be_time={be_time}')
    logging.info(f'fe_time={fe_time}')
    logging.info(f'fe_ratio={fe_time/total_time}')

    msgq.detach()