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
    logging.basicConfig(level=logging.INFO, \
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
    return np.array(image).reshape((1, im_height, im_width, 3)).astype(np.uint8)

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
    selected_image = 'Beach' # @param ['Beach', 'Dogs', 'Naxos Taverna', 'Beatles', 'Phones', 'Birds']
    s = time()
    image = preprocess_image(IMAGES_FOR_TEST[selected_image])
    # s = time()
    for i in range(10):
        # if i % 3 == 0:
        #     image = preprocess_image(IMAGES_FOR_TEST[selected_image])
        results = MODEL(image)
        print(results)
        # result = {key:np.array(value) for key,value in results.items()}
        # classes = [category_index[clazz]['name'] for clazz in result['detection_classes'][0].astype(int)]
        # scores = result['detection_scores'][0]
        # for clazz, score in zip(classes, scores):
        #     print(clazz, score, end=' / ')
        # print('')
    e = time()
    logging.info(f'inference_time={e-s}')

    msgq.detach()    
    i=os.environ.get('CONTAINER_ID')
    boot = round(boot * 1000000)
    import re
    pattern = '(.+)-(.+)-([0-9]{4})'
    program = re.compile(pattern)
    result = program.search(i)
    index = int(result.group(3).lstrip('0'))
    print(f'[parse/boot/ssdresnet50v1/poc/{index}/ready] {boot}')
    finalize()


