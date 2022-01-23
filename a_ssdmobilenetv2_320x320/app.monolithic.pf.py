from time import time
# https://gist.github.com/yrevar/942d3a0ac09ec9e5eb3a
# imagenet index label
import os, sys
import tensorflow as tf
import numpy as np
import logging
import argparse
sys.path.insert(0, '/root/')
CUR_DIR = os.path.dirname(os.path.realpath(__file__))
COCO_DIR = '/root/coco2017'
# # IMG_FILE = '000000581206.jpg' # Hot dogs
# # IMG_FILE = '000000578967.jpg' # Train
IMG_FILE = '000000093965.jpg' # zebra
# # IMG_FILE = '000000104424.jpg' # a woman with a tennis racket
# # IMG_FILE = '000000292446.jpg' # pizza
CLASS_LABLES_FILE = 'imagenet1000_clsidx_to_labels.txt'
CLASSES = {}

from six.moves.urllib.request import urlopen
from six import BytesIO
from PIL import Image

import tensorflow_hub as hub
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


MODEL = None

sys.path.insert(0, '/papi')
from datetime import datetime
TIMESTAMP = datetime.today().strftime('%Y-%m-%d-%H:%M:%S.%f')
import resource
NUM = os.environ.get('NUM')

def configs():
    global IMG_FILE
    logging.basicConfig(level=logging.DEBUG, \
                        format='[%(asctime)s, %(lineno)d %(funcName)s | SSDMobileNetV2] %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', default=IMG_FILE)
    parsed_args = parser.parse_args()
    IMG_FILE = parsed_args.image

    import subprocess, psutil
    cpu_sockets =  int(subprocess.check_output('cat /proc/cpuinfo | grep "physical id" | sort -u | wc -l', shell=True))
    phy_cores = int(psutil.cpu_count(logical=False)/cpu_sockets)
    print(cpu_sockets, phy_cores)

    tf.config.threading.set_inter_op_parallelism_threads(cpu_sockets) # num of sockets: 2
    tf.config.threading.set_intra_op_parallelism_threads(phy_cores) # num of phy cores: 12
    os.environ['OMP_NUM_THREADS'] = str(phy_cores)
    os.environ['KMP_AFFINITY'] = 'granularity=fine,verbose,compact,1,0'

def load_classes():
    global category_index

    with open('/test_images/mscoco_label_map.json', 'r') as f:
        loaded_json = json.load(f)
    category_index = {int(key): value for key, value in loaded_json.items()}


def build_model():
    global MODEL
    # SSD MobileNet v2 320x320
    model_handle = 'https://tfhub.dev/tensorflow/ssd_mobilenet_v2/2'
    MODEL = hub.load(model_handle)

def build_model_mobilenetv2():
    global MODEL

    MODEL = tf.keras.applications.MobileNetV2(input_shape = (224, 224, 3),
                                              include_top = True,
                                              weights = 'imagenet')

def resize_image(file):
    path = os.path.join(COCO_DIR, file)
    # image = tf.keras.preprocessing.image.load_img(path, target_size=(224, 224))
    image = tf.image.decode_image(open(path, 'rb').read())
    image = tf.image.resize(image, (224, 224))
    image = tf.keras.preprocessing.image.img_to_array(image)
    image = tf.expand_dims(image, axis=0)
    image = tf.keras.applications.resnet50.preprocess_input(image)
    return image

def resize_image_mobilenetv2(file):
    path = os.path.join(COCO_DIR, file)
    image = tf.image.decode_image(open(path, 'rb').read())
    image = tf.image.resize(image, (224, 224))
    image = tf.reshape(image, (1, image.shape[0], image.shape[1], image.shape[2]))
    return image


def preprocess_image(path):
    image = None
    if(path.startswith('http')):
        response = urlopen(path)
        image_data = response.read()
        image_data = BytesIO(image_data)
        image = Image.open(image_data)
    else:
        image_data = open(path, 'rb').read()
        # image_data = tf.io.gfile.GFile(path, 'rb').read()
        image = Image.open(BytesIO(image_data))

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
    image = preprocess_image(IMAGES_FOR_TEST[selected_image])
    s = time()
    for i in range(10):
        pf_s = resource.getrusage(resource.RUSAGE_SELF)
        results = MODEL(image)

            # result = {key:value.numpy() for key,value in results.items()}
            # classes = [category_index[clazz]['name'] for clazz in result['detection_classes'][0].astype(int)]
            # scores = result['detection_scores'][0]
            # for clazz, score in zip(classes, scores):
            #     print(clazz, score, end=' / ')
            # print('')
        pf_e = resource.getrusage(resource.RUSAGE_SELF)

        minor_fault = pf_e.ru_minflt - pf_s.ru_minflt
        major_fault = pf_e.ru_majflt - pf_s.ru_majflt
        os.makedirs(f'/data/mon/{NUM}', exist_ok=True)
        with open(f'/data/mon/{NUM}/event-{TIMESTAMP}-PF.log', 'a') as f:
            print(f'{minor_fault}, {major_fault}')
            f.write(f'{minor_fault}, {major_fault}\n')
    e = time()
    logging.info(f'inference_time={e-s}')
