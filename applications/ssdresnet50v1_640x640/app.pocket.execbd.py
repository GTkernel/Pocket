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
# https://www.tensorflow.org/hub/tutorials/tf2_object_detection
CUR_DIR = os.path.dirname(os.path.realpath(__file__))
COCO_DIR = '/root/coco2017'
# IMG_FILE = '000000581206.jpg' # Hot dogs
# IMG_FILE = '000000578967.jpg' # Train
IMG_FILE = '000000093965.jpg' # zebra
# IMG_FILE = '000000104424.jpg' # a woman with a tennis racket
# IMG_FILE = '000000292446.jpg' # pizza
CLASS_LABLES_FILE = 'imagenet1000_clsidx_to_labels.txt'
CLASSES = {}
MODEL: TFDataType.Model
msgq = PocketMessageChannel.get_instance()


from six.moves.urllib.request import urlopen
from six import BytesIO
from PIL import Image

import json
category_index = None

IMAGES_FOR_TEST = {
  'Beach' : '/test_images/image2.jpg',
  'Dogs' : '/test_images/image1.jpg',
  # By Heiko Gorski, Source: https://commons.wikimedia.org/wiki/File:Naxos_Taverna.jpg
  'Naxos Taverna' : '/test_images/Naxos_Taverna.jpg',
  # Source: https://commons.wikimedia.org/wiki/File:The_Coleoptera_of_the_British_islands_(Plate_125)_(8592917784).jpg
  'Beatles' : '/test_images/The_Coleoptera_of_the_British_islands_(Plate_125)_(8592917784).jpg',
  # By Américo Toledano, Source: https://commons.wikimedia.org/wiki/File:Biblioteca_Maim%C3%B3nides,_Campus_Universitario_de_Rabanales_007.jpg
  'Phones' : '/test_images/1024px-Biblioteca_Maimónides,_Campus_Universitario_de_Rabanales_007.jpg',
  # Source: https://commons.wikimedia.org/wiki/File:The_smaller_British_birds_(8053836633).jpg
  'Birds' : '/test_images/The_smaller_British_birds_(88053836633).jpg',
}

def configs():
    global IMG_FILE
    logging.basicConfig(level=logging.DEBUG, \
                        format='[%(asctime)s, %(lineno)d %(funcName)s | SSDResNetV1] %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', default=IMG_FILE)
    parsed_args = parser.parse_args()
    IMG_FILE = parsed_args.image

def load_classes():
    global category_index

    with open('/test_images/mscoco_label_map.json', 'r') as f:
        loaded_json = json.load(f)
    category_index = {int(key): value for key, value in loaded_json.items()}

def build_model():
    global MODEL

    # SSD ResNet50 V1 FPN 640x640 (RetinaNet50)
    model_handle = 'https://tfhub.dev/tensorflow/retinanet/resnet50_v1_fpn_640x640/1'
    MODEL = msgq.hub_load(model_handle)

def preprocess_image(path):
    image = None
    image = Image.open(path)

    (im_width, im_height) = image.size
    return np.array(image.getdata()).reshape((1, im_height, im_width, 3)).astype(np.uint8)

if __name__ == '__main__':
    configs()
    load_classes()

    s = time()
    build_model()
    e = time()
    logging.info(f'graph_construction_time={e-s}')
    selected_image = 'Beach' # @param ['Beach', 'Dogs', 'Naxos Taverna', 'Beatles', 'Phones', 'Birds']
    import cProfile, pstats, io
    pr = cProfile.Profile()
    pr.enable()
    for i in range(10):
        if i % 3 == 0:
            image = preprocess_image(IMAGES_FOR_TEST[selected_image])
        results = MODEL(image)
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


