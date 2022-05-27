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

class IsolationControl:
    NAMESPACE = True if os.environ.get('NSCREATE', 'on') == 'on' else False
    PRIVATEQUEUE = True if os.environ.get('PRIVATEQUEUE', 'on') == 'on' else False
    CAPABILITIESLIST = True if os.environ.get('CAPABILITIESLIST', 'on') == 'on' else False

if not IsolationControl.NAMESPACE or not IsolationControl.PRIVATEQUEUE or not IsolationControl.CAPABILITIESLIST:

    from yolo_msgq_isolation import PocketMessageChannel, Utils
else:
    from yolo_msgq import PocketMessageChannel, Utils
    
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

def finalize():
    # if 'cProfile' in dir():
    #     cProfile.create_stats()
    stat_dict = Utils.measure_resource_usage()
    print('[resource_usage]', f'cputime.total={stat_dict.get("cputime.total", None)}')
    print('[resource_usage]', f'cputime.user={stat_dict.get("cputime.user", None)}')
    print('[resource_usage]', f'cputime.sys={stat_dict.get("cputime.sys", None)}')
    print('[resource_usage]', f'memory.max_usage={stat_dict.get("memory.max_usage", None)}')
    print('[resource_usage]', f'memory.memsw.max_usage={stat_dict.get("memory.memsw.max_usage", None)}')
    print('[resource_usage]', f'memory.stat.pgfault={stat_dict.get("memory.stat.pgfault", None)}')
    print('[resource_usage]', f'memory.stat.pgmajfault={stat_dict.get("memory.stat.pgmajfault", None)}')
    print('[resource_usage]', f'memory.failcnt={stat_dict.get("memory.failcnt", None)}')
    sys.stdout.flush()
    os._exit(0)

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
    s = time()
    with open('psycho.txt') as f:
        roger_ebert_hitchcock_psycho = f.readlines()
    reloaded_results = msgq.tf_sigmoid(reloaded_model(msgq.tf_constant(roger_ebert_hitchcock_psycho)))
    e = time()
    # print_my_examples(roger_ebert_hitchcock_psycho, reloaded_results)
    logging.info(f'inference_time={e-s}')
    msgq.detach()
    finalize()