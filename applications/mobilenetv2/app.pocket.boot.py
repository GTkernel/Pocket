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
from PIL import Image

def configs():
    global IMG_FILE
    logging.basicConfig(level=logging.DEBUG, \
                        format='[%(asctime)s, %(lineno)d %(funcName)s | MobileNetV2] %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', default=IMG_FILE)
    parsed_args = parser.parse_args()
    IMG_FILE = parsed_args.image

def load_classes():
    with open(CLASS_LABLES_FILE) as file:
        raw_labels = file.read().replace('{', '').replace('}', '').split('\n')
        for line in raw_labels:
            key, value = line.split(':')
            value = value.replace('\'', '').strip()
            if value[-1] is ',':
                value = value[:-1]

            CLASSES[int(key)] = value

def build_model():
    global MODEL
    MODEL = msgq.tf_keras_applications_MobileNetV2(input_shape = (224, 224, 3),
                                                   include_top = True,
                                                   weights = 'imagenet')

def resize_image(file):
    path = os.path.join(COCO_DIR, file)
    image = Image.open(path)
    image = image.resize((224, 224))
    return np.array(image).reshape((1, 224, 224, 3)).astype(np.float32)

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
    load_classes()
    s = time()
    build_model()
    boot = e = time()
    logging.info(f'graph_construction_time={e-s}')
    image = resize_image(IMG_FILE)
    s = time()
    for i in range(10):
        result = MODEL(image)
    e = time()
    logging.info(f'inference_time={e-s}')
    cls = msgq.np_argmax(result)
    logging.info(f'{CLASSES[cls]}')
    msgq.detach()
    
    i=os.environ.get('CONTAINER_ID')
    boot = round(boot * 1000000)
    import re
    pattern = '(.+)-(.+)-([0-9]{4})'
    program = re.compile(pattern)
    result = program.search(i)
    index = int(result.group(3).lstrip('0'))
    print(f'[parse/boot/mobilenetv2/poc/{index}/ready] {boot}')
    finalize()