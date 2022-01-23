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
    image = msgq.tf_image_decode__image(open(path, 'rb').read()) / 255
    image = msgq.tf_image_resize(image, (224, 224))
    image = msgq.tf_reshape(image, (1, image.shape[0], image.shape[1], image.shape[2]))
    return image

if __name__ == '__main__':
    configs()
    load_classes()
    s = time()
    build_model()
    e = time()
    logging.info(f'graph_construction_time={e-s}')

    import cProfile, pstats, io
    pr = cProfile.Profile()
    pr.enable()    
    for i in range(10):
        image = resize_image(IMG_FILE)
        result = MODEL(image)
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
    
    cls = msgq.np_argmax(result)
    logging.info(f'{CLASSES[cls]}')
    msgq.detach()