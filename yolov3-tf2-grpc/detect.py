# def debug(*args):
#     import inspect
#     filename = inspect.stack()[1].filename
#     lineno = inspect.stack()[1].lineno
#     caller = inspect.stack()[1].function
#     print(f'debug>> [{filename}:{lineno}, {caller}]', *args)

def make_json(container_id):
    import json
    args_dict = {}

    args_dict['type']='closed-proc-ns'
    args_dict['cid']=container_id
    args_dict['events']=['cpu-cycles','page-faults','minor-faults','major-faults','cache-misses','LLC-load-misses','LLC-store-misses','dTLB-load-misses','iTLB-load-misses','instructions']

    args_json = json.dumps(args_dict)

    return args_json

def connect_to_perf_server():
    import socket
    PERF_SERVER_SOCKET = '/sockets/perf_server.sock'
    container_id = socket.gethostname()
    my_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    my_socket.connect(PERF_SERVER_SOCKET)
    json_data_to_send = make_json(container_id)
    my_socket.sendall(json_data_to_send.encode('utf-8'))
    data_received = my_socket.recv(1024)
    # debug(data_received)
    my_socket.close()
    
def get_container_id():
    cg = open('/proc/self/cgroup')
    content = cg.readlines()
    for line in content:
        if 'docker' in line:
            cid = line.strip().split('/')[-1]
            # debug(cid)
            return cid




# connect_to_perf_server()

import time, subprocess
from absl import app, flags, logging
from absl.flags import FLAGS
# import cv2 ###
import numpy as np
# import tensorflow as tf ###
from yolov3_tf2.models import (
    YoloV3, YoloV3Tiny, YoloV32
)
from yolov3_tf2.dataset import transform_images, transform_images2, load_tfrecord_dataset
from yolov3_tf2.utils import draw_outputs


import logging
import grpc
import sys, os

# Todo: remove ## POCKET_GRPC
# sys.path.insert(0, os.path.abspath('../tfrpc/client'))
# import yolo_pb2
# import yolo_pb2_grpc
# from tf_wrapper import TFWrapper, ControlProcedure

## preinit
CONTAINER_ID = get_container_id()
from yolo_msgq import SharedMemoryChannel, PocketMessageChannel
from pocket_tf_if import *

if sys.argv[2] == 'shmem':
    # shmem = SharedMemoryChannel(key=CONTAINER_ID, size=FLAGS.num_images * FLAGS.size_to_transfer)
    shmem = SharedMemoryChannel(key=int(CONTAINER_ID[:8], 16), size=1 * (32 + 4 * 1024 * 1024), path=sys.argv[4])
else:
    shmem = None


CHUNK_SIZE = 4000000 # approximation to 4194304, grpc message size limit

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

# POCKET_GRPC
# g_stub: yolo_pb2_grpc.YoloTensorflowWrapperStub

# # g_redis: redis.Redis
# # CONTAINER_ID: str
# # shmem = None
DATA_CHANNEL = None


def initialize(stub, server_addr, data_channel):
    global g_stub, CONTAINER_ID, DATA_CHANNEL

    # CONTAINER_ID = get_container_id()
    # config_data_channel(data_channel, int(CONTAINER_ID[:8], 16))

    ControlProcedure.Connect(stub, FLAGS.object, CONTAINER_ID, shmem_channel=shmem) # path, bin, redis, shmem
    g_stub = stub
    signal.signal(signal.SIGINT, finalize)
    DATA_CHANNEL=data_channel

# def initialize_msgq(message_queue):
    


def finalize():
    ControlProcedure.Disconnect(g_stub)
    if DATA_CHANNEL == 'shmem':
        shmem.finalize()

def finalize_msgq():
    msgq = PocketMessageChannel.get_instance()
    msgq.detach()
    
def main(_argv):
    # time1 = time.time()
    if FLAGS.comm == 'grpc':
        # os.environ['SERVER_ADDR'] = 'localhost' # todo: remove after debugging
        server_addr = os.environ.get('SERVER_ADDR')
        channel = grpc.insecure_channel(f'{server_addr}:1990', \
            options=[('grpc.max_send_message_length', 4 * 1024 * 1024), \
            ('grpc.max_receive_message_length', 4 * 1024 * 1024), \
            ('grpc.max_message_length', 4 * 1024 * 1024)] \
        )
        stub = yolo_pb2_grpc.YoloTensorflowWrapperStub(channel)
        initialize(stub, server_addr, FLAGS.object)
    elif FLAGS.comm == 'msgq':
        msgq = PocketMessageChannel.get_instance()
        # Todo: remove. below function is just for debugging purpose.
        # Or, transform to initial estabilshment of connection
        # msgq.hello('misun')
        # msgq.hello_via_lq('misun local')
    else:
        raise Exception('unknown communication channel. comm parameter should be defined as either \'--comm=grpc\' or \'--comm=msgq\'.')
    # time1_1 = time.time()
    # exit()

    if FLAGS.hello:
        health = ControlProcedure.SayHello(stub, 'misun')
        exit()
    # physical_devices = tf.config.experimental.list_physical_devices('GPU')
    if FLAGS.comm == 'grpc':
        physical_devices = TFWrapper.tf_config_experimental_list__physical__devices(stub, device_type='GPU')
    elif FLAGS.comm == 'msgq':
        physical_devices = msgq.tf_config_experimental_list__physical__devices('GPU')
    # time1_2 = time.time()

    if len(physical_devices) > 0: # in my settings, this if statement always returns false
        # tf.config.experimental.set_memory_growth(physical_devices[0], True) 
        if FLAGS.comm == 'grpc':
            TFWrapper.tf_config_experimental_set__memory__growth(physical_devices[0], True) 
        elif FLAGS.comm == 'msgq':
            PocketMessageChannel.get_instance().tf_config_experimental_set__memory__growth(physical_devices[0], True)

    # time2 = time.time()
    graph_construction_start = time.time()
    if FLAGS.tiny:
        yolo = YoloV3Tiny(classes=FLAGS.num_classes)
        # yolo = YoloV3Tiny(stub=stub, classes=FLAGS.num_classes)
    else:
        # yolo = YoloV3(classes=FLAGS.num_classes)
        if FLAGS.comm == 'grpc':
            yolo = YoloV3(stub=stub, classes=FLAGS.num_classes)
        elif FLAGS.comm == 'msgq':
            yolo = YoloV32(classes=FLAGS.num_classes)
    # time3 = time.time()

    # yolo.load_weights(FLAGS.weights).expect_partial()
    if FLAGS.comm == 'grpc':
        status_obj_id = TFWrapper.attribute_model_load__weights(stub, 'yolov3', FLAGS.weights) ## todo check if already weighted
        TFWrapper.attribute_checkpoint_expect__partial(stub, status_obj_id)
    elif FLAGS.comm == 'msgq':
        yolo.load_weights(FLAGS.weights)
    logging.info('weights loaded')
    graph_construction_end = time.time()
    logging.info(f'graph_construction_time: {graph_construction_end-graph_construction_start}')
    # time4 = time.time()

    class_names = [c.strip() for c in open(FLAGS.classes).readlines()]
    logging.info('classes loaded')

    if FLAGS.tfrecord:
        logging.info('this branch?')
        dataset = load_tfrecord_dataset(
            FLAGS.tfrecord, FLAGS.classes, FLAGS.size)
        dataset = dataset.shuffle(512)
        img_raw, _label = next(iter(dataset.take(1)))
    else:
        # img_raw = tf.image.decode_image(
        #     open(FLAGS.image, 'rb').read(), channels=3)
        # start=time.time()
        if FLAGS.comm == 'grpc':
            if FLAGS.object == 'bin':
                img_raw = TFWrapper.tf_image_decode__image(stub, 
                    channels=3, data_channel=FLAGS.object, data_bytes=open(FLAGS.image, 'rb').read())
            elif FLAGS.object == 'path':
                img_raw = TFWrapper.tf_image_decode__image(stub, image_path=FLAGS.image, 
                    channels=3, data_channel=FLAGS.object)
            elif FLAGS.object == 'shmem':
                img_raw = TFWrapper.tf_image_decode__image(stub, #image_path=FLAGS.image, 
                    channels=3, data_channel=FLAGS.object, data_size_in_byte=FLAGS.size_to_transfer, shmem=shmem)
            else:
                raise Exception(f'Unknown data channel={FLAGS.object}')
        elif FLAGS.comm == 'msgq':
            img_raw = PocketMessageChannel.get_instance().tf_image_decode__image(open(FLAGS.image, 'rb').read(), channels=3)
            
        # end=time.time()
        # logging.info(f'time={end-start}')

    # img = tf.expand_dims(img_raw, 0)
    if FLAGS.comm == 'grpc':
        img = TFWrapper.tf_expand__dims(stub, img_raw, 0)
        img = transform_images(stub, img, FLAGS.size)

        t1 = time.time()
        # boxes, scores, classes, nums = yolo(img)
        img_obj_wrapper = yolo_pb2.CallRequest.ObjId()
        img_obj_wrapper.obj_id, img_obj_wrapper.release = img, False
        # ret_val = TFWrapper.callable_emulator(stub, yolo, True, 1, 'yolov3', img_obj_wrapper)
        # ret_val = TFWrapper.iterable_indexing(stub, ret_val, 0)
        # boxes, scores, classes, nums = ret_val
        boxes, scores, classes, nums = TFWrapper.callable_emulator(stub, yolo, True, 1, 'yolov3', img_obj_wrapper)
        t2 = time.time()
        logging.info('inference_time: {}'.format(t2 - t1))

        logging.info('detections:')
        for i in range(nums[0]):
            logging.info('\t{}, {}, {}'.format(class_names[int(classes[0][i])],
                                                np.array(scores[0][i]),
                                                np.array(boxes[0][i])))

        # # # img = cv2.cvtColor(img_raw.numpy(), cv2.COLOR_RGB2BGR)
        # # img_raw_numpy = TFWrapper.byte_tensor_to_numpy(stub, img_raw)

        # # # img = cv2.cvtColor(img_raw_numpy, cv2.COLOR_RGB2BGR)
        # # # img = draw_outputs(img, (boxes, scores, classes, nums), class_names)
        # # # cv2.imwrite(FLAGS.output, img)

        # # img_result = cv2.cvtColor(img_raw_numpy, cv2.COLOR_RGB2BGR)
        # # img_result = draw_outputs(img_result, (boxes, scores, classes, nums), class_names)
        # # cv2.imwrite(FLAGS.output, img_result)

        # # logging.info('output saved to: {}'.format(FLAGS.output))

        finalize()
    elif FLAGS.comm == 'msgq':
        img = PocketMessageChannel.get_instance().tf_expand__dims(img_raw, 0)
        img = transform_images2(img, FLAGS.size)
        # time5 = time.time()

        t1 = time.time()
        boxes, scores, classes, nums = yolo(img)
        t2 = time.time()
        logging.info('inference_time: {}'.format(t2 - t1))

        logging.info('detections:')
        for i in range(nums[0]):
            logging.info('\t{}, {}, {}'.format(class_names[int(classes[0][i])],
                                                np.array(scores[0][i]),
                                                np.array(boxes[0][i])))

        # time6 = time.time()
        finalize_msgq()
    # time7 = time.time()
    # logging.info(f'time1={time2-time1}')
    # logging.info(f'time2={time3-time2}')
    # logging.info(f'time3={time4-time3}')
    # logging.info(f'time4={time5-time4}')
    # logging.info(f'time5={time6-time5}')
    # logging.info(f'time6={time7-time6}')

    # logging.info(f'time1.1={time1_1-time1}')
    # logging.info(f'time1.2={time1_2-time1_1}')
    # logging.info(f'time1.3={time2-time1_2:f}')
    exit()
      


if __name__ == '__main__':
    try:
        logging.basicConfig(level=logging.INFO)
        # logging.basicConfig(level=logging.CRITICAL)
        app.run(main)
    except SystemExit:
        pass
