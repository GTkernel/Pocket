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
IMG_FILE = '000000093965.jpg' # zebra
# IMG_FILE = '000000104424.jpg' # a woman with a tennis racket
# IMG_FILE = '000000292446.jpg' # pizza
CLASS_LABLES_FILE = 'imagenet1000_clsidx_to_labels.txt'
CLASSES = {}
MODEL: TFDataType.Model
msgq = PocketMessageChannel.get_instance()

def configs():
    global IMG_FILE
    logging.basicConfig(level=logging.DEBUG, \
                        format='[%(asctime)s, %(lineno)d %(funcName)s | ResNet50] %(message)s')
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

# def build_model():
#     global MODEL
#     try:
#         # Invalid # keras_model = tf.Graph.get_tensor_by_name('yolov3')
#         is_exist, keras_model = PocketMessageChannel.get_instance().check_if_model_exist('mobilenetv2')
#     except KeyError as e:
#         is_exist = False

#     if is_exist:
#         MODEL = keras_model
#     else:
#         MODEL = msgq.tf_keras_applications_MobileNetV2(input_shape = (224, 224, 3),
#                                                     include_top = True,
#                                                     weights = 'imagenet')
def build_model():
    global MODEL
    MODEL = msgq.tf_keras_applications_ResNet50(input_shape = (224, 224, 3),
                                                include_top = True,
                                                weights = 'imagenet')

# def resize_image(file):
#     path = os.path.join(COCO_DIR, file)
#     image = msgq.tf_image_decode__image(open(path, 'rb').read()) / 255
#     image = msgq.tf_image_resize(image, (224, 224))
#     image = msgq.tf_reshape(image, (1, image.shape[0], image.shape[1], image.shape[2]))
#     return image

def resize_image(file):
    path = os.path.join(COCO_DIR, file)
    image = msgq.tf_image_decode__image(open(path, 'rb').read())
    image = msgq.tf_image_resize(image, (224, 224))
    image = msgq.tf_keras_preprocessing_image_img__to__array(image)
    image = msgq.tf_expand__dims(image, axis=0)
    image = msgq.tf_keras_applications_resnet50_preprocess__input(image)

    return image

def build_model_mobilenetv2():
    global MODEL

    MODEL = msgq.tf_keras_applications_MobileNetV2(input_shape = (224, 224, 3),
                                                   include_top = True,
                                                   weights = 'imagenet')

def resize_image_mobilenetv2(file):
    path = os.path.join(COCO_DIR, file)
    image = msgq.tf_image_decode__image(open(path, 'rb').read())
    image = msgq.tf_image_resize(image, (224, 224))
    image = msgq.tf_reshape(image, (1, image.shape[0], image.shape[1], image.shape[2]))
    return image

if __name__ == '__main__':
    configs()
    load_classes()

    s = time()
    build_model()
    e = time()
    # logging.info(f'graph_construction_time={e-s:.6f}')
    image = resize_image(IMG_FILE)
    s = time()
    for i in range(10):
        result = MODEL(image)
    e = time()
    logging.info(f'inference_time={e-s:.6f}')
    cls = msgq.np_argmax(result)
    # logging.info(f'{CLASSES[cls]}')

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
    
    msgq.detach()