    
def get_container_id():
    cg = open('/proc/self/cgroup')
    content = cg.readlines()
    for line in content:
        if 'docker' in line:
            cid = line.strip().split('/')[-1]
            # debug(cid)
            return cid




# connect_to_perf_server()

import time
from absl import app, flags, logging
from absl.flags import FLAGS
# import cv2 ###
import numpy as np
# import tensorflow as tf ###
from yolov3_tf2.models import (
    YoloV3, YoloV3Tiny, YoloV32
)
from yolov3_tf2.dataset import transform_images2, load_tfrecord_dataset


import logging
# import grpc
import sys, os

## preinit
CONTAINER_ID = get_container_id()
from yolo_msgq import SharedMemoryChannel, PocketMessageChannel
from pocket_tf_if import *

# if sys.argv[2] == 'shmem':
#     # shmem = SharedMemoryChannel(key=CONTAINER_ID, size=FLAGS.num_images * FLAGS.size_to_transfer)
#     shmem = SharedMemoryChannel(key=int(CONTAINER_ID[:8], 16), size=1 * (32 + 4 * 1024 * 1024), path=sys.argv[4])
# else:
#     shmem = None


# CHUNK_SIZE = 4000000 # approximation to 4194304, grpc message size limit

flags.DEFINE_string('classes', './data/coco.names', 'path to classes file')
flags.DEFINE_string('weights', './checkpoints/yolov3.tf',
                    'path to weights file')
flags.DEFINE_boolean('tiny', False, 'yolov3 or yolov3-tiny')
flags.DEFINE_integer('size', 416, 'resize images to')
flags.DEFINE_string('image', './data/girl.png', 'path to input image')
flags.DEFINE_string('tfrecord', None, 'tfrecord instead of image')
flags.DEFINE_string('output', './output.jpg', 'path to output image')
flags.DEFINE_integer('num_classes', 80, 'number of classes in the model')

# Misun defined
PERF_SERVER_SOCKET = '/sockets/perf_server.sock'
flags.DEFINE_boolean('hello', False, 'hello or health check')
flags.DEFINE_string('object', 'path', 'specify how to pass over objects')
flags.DEFINE_integer('num_images', 1, 'the number of images to process')
flags.DEFINE_integer('size_to_transfer', 4*1024*1024, 'the size of image')
flags.DEFINE_string('comm', 'msgq', 'specify communication channel, can be either msgq or grpc')

def finalize_msgq():
    msgq = PocketMessageChannel.get_instance()
    msgq.detach()

class GraphConstruct(object):
    def __init__(self, msgq):
        self.msgq = msgq

    def __enter__(self):
        self.msgq.start_build_graph()

    def __exit__(self, type, value, trace_back):
        self.msgq.end_build_graph()
    
def main(_argv):
    logging.info('app starts')
    msgq = PocketMessageChannel.get_instance()

    physical_devices = msgq.tf_config_experimental_list__physical__devices('GPU')

    if len(physical_devices) > 0: # in my settings, this if statement always returns false
        PocketMessageChannel.get_instance().tf_config_experimental_set__memory__growth(physical_devices[0], True)

    # time2 = time.time()
    graph_construction_start = time.time()
    with GraphConstruct(msgq):
        yolo = YoloV32(classes=FLAGS.num_classes)

        yolo.load_weights(FLAGS.weights)
    logging.info('weights loaded')
    graph_construction_end = time.time()
    logging.info(f'graph_construction_time: {graph_construction_end-graph_construction_start}')
    # time4 = time.time()

    class_names = [c.strip() for c in open(FLAGS.classes).readlines()]
    logging.info('classes loaded')

    img_raw = PocketMessageChannel.get_instance().tf_image_decode__image(open(FLAGS.image, 'rb').read(), channels=3)
            
    img = PocketMessageChannel.get_instance().tf_expand__dims(img_raw, 0)
    img = transform_images2(img, FLAGS.size)

    t1 = time.time()
    for i in range(10):
        logging.info(i)
        boxes, scores, classes, nums = yolo(img)
    t2 = time.time()
    logging.info('inference_time: {}'.format(t2 - t1))

    logging.info('detections:')
    for i in range(nums[0]):
        logging.info('\t{}, {}, {}'.format(class_names[int(classes[0][i])],
                                            np.array(scores[0][i]),
                                            np.array(boxes[0][i])))
    finalize_msgq()
      
def clone_main():
    try:
        logging.basicConfig(level=logging.INFO)
        # logging.basicConfig(level=logging.CRITICAL)
        app.run(main)
        return 0
    except SystemExit:
        return 0



if __name__ == '__main__':
    try:
        logging.basicConfig(level=logging.INFO)
        # logging.basicConfig(level=logging.CRITICAL)
        app.run(main)
    except SystemExit:
        pass
