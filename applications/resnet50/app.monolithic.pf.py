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
# IMG_FILE = '000000581206.jpg' # Hot dogs
# IMG_FILE = '000000578967.jpg' # Train
IMG_FILE = '000000093965.jpg' # zebra
# IMG_FILE = '000000104424.jpg' # a woman with a tennis racket
# IMG_FILE = '000000292446.jpg' # pizza
CLASS_LABLES_FILE = 'imagenet1000_clsidx_to_labels.txt'
CLASSES = {}
MODEL: tf.keras.applications.ResNet50

sys.path.insert(0, '/papi')
from datetime import datetime
TIMESTAMP = datetime.today().strftime('%Y-%m-%d-%H:%M:%S.%f')
import resource
NUM = os.environ.get('NUM')

def configs():
    global IMG_FILE
    logging.basicConfig(level=logging.DEBUG, \
                        format='[%(asctime)s, %(lineno)d %(funcName)s | ResNet50] %(message)s')
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

    MODEL = tf.keras.applications.ResNet50(input_shape = (224, 224, 3),
                                              include_top = True,
                                              weights = 'imagenet')

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

if __name__ == '__main__':
    configs()
    load_classes()

    s = time()
    build_model()
    e = time()
    logging.info(f'graph_construction_time={e-s}')
    image = resize_image(IMG_FILE)
    s = time()
    for i in range(10):
        pf_s = resource.getrusage(resource.RUSAGE_SELF)
        result = MODEL(image)
        pf_e = resource.getrusage(resource.RUSAGE_SELF)

        minor_fault = pf_e.ru_minflt - pf_s.ru_minflt
        major_fault = pf_e.ru_majflt - pf_s.ru_majflt
        os.makedirs(f'/data/mon/{NUM}', exist_ok=True)
        with open(f'/data/mon/{NUM}/event-{TIMESTAMP}-PF.log', 'a') as f:
            print(f'{minor_fault}, {major_fault}')
            f.write(f'{minor_fault}, {major_fault}\n')
    e = time()
    logging.info(f'inference_time={e-s}')
    cls = np.argmax(result)
    logging.info(f'{CLASSES[cls]}')


    # s = time()
    # build_model_mobilenetv2()
    # e = time()
    # logging.info(f'graph_construction_time={e-s}')
    # image = resize_image_mobilenetv2(IMG_FILE)
    # s = time()
    # for i in range(10):
    #     result = MODEL(image)
    # e = time()
    # logging.info(f'inference_time={e-s}')
    # cls = np.argmax(result)
    # logging.info(f'{CLASSES[cls]}')