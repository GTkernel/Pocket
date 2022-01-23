#!/usr/bin/python
import os
import subprocess, time
import socket
# from multiprocessing import Process # todo: remove?

# todo: remove these after debugging
# os.environ['YOLO_SERVER'] = '1'
# from multiprocessing import Process, Pipe, Manager
# import time
# import contexttimer
# def child_process(func):
#     """Makes the function run as a separate process."""
#     def wrapper(*args, **kwargs):
#         def worker(conn, func, args, kwargs):
#             conn.send(func(*args, **kwargs))
#             conn.close()
#         parent_conn, child_conn = Pipe()
#         p = Process(target=worker, args=(child_conn, func, args, kwargs))
#         p.start()
#         ret = parent_conn.recv()
#         p.join()
#         return ret
#     return wrapper

from concurrent import futures
import logging
import grpc
import signal

import yolo_pb2, yolo_pb2_grpc
import pickle

from absl import flags
from absl.flags import FLAGS

import tensorflow as tf
# tf.enable_eager_execution()
import numpy as np
from tensorflow.keras import Model
from tensorflow.keras.layers import (
    Add,
    Concatenate,
    Conv2D,
    Input,
    Lambda,
    LeakyReLU,
    MaxPool2D,
    UpSampling2D,
    ZeroPadding2D,
)

from tensorflow.keras.regularizers import l2
from tensorflow.keras.losses import (
    binary_crossentropy,
    sparse_categorical_crossentropy
)

import sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from models import YoloV3

# sys.path.insert(0, os.path.abspath('../../yolov3_tf2'))
# os.chdir('../../yolov3-tf2')
# sys.path.insert(0, os.path.abspath('yolov3_tf2'))
# print(os.getcwd()) ##
from batch_norm import BatchNormalization
from utils import broadcast_iou
import threading
from enum import Enum
from sysv_ipc import Semaphore, SharedMemory, MessageQueue, IPC_CREX
# os.chdir(cwd)
# from collections.abc import Iterable
# import inspect



yolo_anchors = np.array([(10, 13), (16, 30), (33, 23), (30, 61), (62, 45),
                         (59, 119), (116, 90), (156, 198), (373, 326)],
                        np.float32) / 416
yolo_anchor_masks = np.array([[6, 7, 8], [3, 4, 5], [0, 1, 2]])

flags.DEFINE_integer('yolo_max_boxes', 100,
                     'maximum number of boxes per image')
flags.DEFINE_float('yolo_iou_threshold', 0.5, 'iou threshold')
flags.DEFINE_float('yolo_score_threshold', 0.5, 'score threshold')

flags.DEFINE_string('classes', './data/coco.names', 'path to classes file')
flags.DEFINE_string('weights', './checkpoints/yolov3.tf',
                    'path to weights file')
flags.DEFINE_boolean('tiny', False, 'yolov3 or yolov3-tiny')
flags.DEFINE_integer('size', 416, 'resize images to')
flags.DEFINE_string('image', './data/girl.png', 'path to input image')
flags.DEFINE_string('tfrecord', None, 'tfrecord instead of image')
flags.DEFINE_string('output', './output.jpg', 'path to output image')
flags.DEFINE_integer('num_classes', 80, 'number of classes in the model')

class OBJECT_PASS_T(Enum):
    BINARY = 1;
    PATH = 2;
    REDIS_OBJ_ID = 3;
    SHMEM = 4;

class Container_Info:
    def __init__(self, container_id, object_pass, subdir):
        self.container_id = container_id
        self.object_pass = object_pass
        self.object_ownership = {}
        self.subdir = subdir

        if object_pass == OBJECT_PASS_T.SHMEM:
            self.sem = Semaphore(int(container_id[:8], 16))
            self.shmem = SharedMemory(int(container_id[:8], 16))
            self.mv = memoryview(self.shmem)

    def __str___(self):
        return f'container_id={self.container_id}\n' + \
               f'object_pass={self.object_pass}\n' + \
               f'object_ownership={len(self.object_ownership)}\n' + \
               f'subdir={self.subdir}\n' + \
               f'have shmem={self.shmem is not None}\n'


    def write(self, content):
        if self.object_pass == OBJECT_PASS_T.SHMEM:
            self.sem.acquire()
            self.shmem.write(content)
            self.sem.release()
        else:
            raise Exception('Valid only for shmem channel!')

    def read(self, size):
        if self.object_pass == OBJECT_PASS_T.SHMEM:
            self.sem.acquire()
            # data = self.shmem.read(size)
            data = bytes(self.mv[32:32+self.__data_length()])
            # data = self.mv[32:32+self.__data_length()]
            self.sem.release()
            return data
        else:
            raise Exception('Valid only for shmem channel!')

    def __data_length(self):
        if self.object_pass == OBJECT_PASS_T.SHMEM:
            length = int.from_bytes(self.mv[0:4], 'little')
            return length
        else:
            raise Exception('Valid only for shmem channel!')

    def view(self, size):
        if self.object_pass == OBJECT_PASS_T.SHMEM:
            self.sem.acquire()
            data = self.mv[32:32+self.__data_length()]
            self.sem.release()
            return data
        else:
            raise Exception('Valid only for shmem channel!')



##### Misun Defined
PERF_SERVER_SOCKET = '/sockets/perf_server.sock'
OBJECT_PASS: OBJECT_PASS_T

## Todo: need to be moved into PocketManager;
## global variables
Model_Create_Lock = threading.Lock()
Weights_Load_Lock = threading.Lock()
Graph_Build_In_Progress = False
Container_Id = "";

universal_key = 0x1001 # key for message queue

Global_Tensor_Dict = {}
Object_Ownership = {}
# Global_Graph_Dict = {}
# Global_Sess_Dict = {}
# Global_Model_Dict = Manager().dict()
Global_Model_Dict = {}
Container_Id_Dict = {}
Subdir_Dict = {}
hostroot = '/layers/'

conv2d_count = 0
batch_norm_count = 0
leaky_re_lu_count = 0
zero_padding2d_count=0
add_count = 0
lambda_count = 0

class ModelInfo:
    class State(Enum):
        BUILD_IN_PROGRESS = 1
        BUILD_DONE = 2
        LOAD_WEIGHT_DONE = 3

    def __init__(self, name, container_id):
        self.name = name
        self.container_id = container_id
        self.state = ModelInfo.State.BUILD_IN_PROGRESS
        self.obj_id = -1
        self.is_weight_loaded = False
        self.weight_checkpoint = None

    def set_done(self, model):
        global Graph_Build_In_Progress, Container_Id

        self.state = ModelInfo.State.BUILD_DONE
        Graph_Build_In_Progress = False
        Container_Id = ""
        self.model = model
        self.obj_id = id(model)

    def is_done(self):
        return self.state

    def load_weights(self, model, weights_path):
        if self.is_weight_loaded:
            return self.weight_checkpoint
        else:
            with Weights_Load_Lock:
                self.weight_checkpoint = model.load_weights(weights_path)
                self.state = ModelInfo.State.LOAD_WEIGHT_DONE
                self.is_weight_loaded = True
            return self.weight_checkpoint

    def is_weight_loaded(self, model):
        return self.is_weight_loaded

class IllegalModelBuildException(Exception):
    def __init__(self):
        pass

    def __str__(self):
        return 'IllegalModelBuildException'

class PocketModel(tf.keras.Model):
    def call(self, inputs, training=False, sendpipe=None):
        # # print(type(self))
        # # print(inputs)
        # ret_val = super(tf.keras.Model, self).__call__(inputs, training)
        # # print('there')
        # return ret_val

        ret_val = super().call(inputs, training)
        if sendpipe != None:
            sendpipe.send(ret_val)
            sendpipe.close()
        return ret_val

class Color:
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    DARKCYAN = '\033[36m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def utils_get_obj(obj_id: int):
    return Global_Tensor_Dict[obj_id]

def utils_set_obj(obj, container_id):
    obj_id: int = id(obj)
    Global_Tensor_Dict[obj_id] = obj
    if container_id in Object_Ownership:
        Object_Ownership[container_id].append(obj_id)
    else:
        Object_Ownership[container_id] = [obj_id]
    return obj_id

def utils_rm_obj(obj_ids):
    for obj_id in obj_ids:
        del Global_Tensor_Dict[obj_id]

def utils_is_iterable(obj):
    try:
        _ = (e for e in obj)
        return True
    except TypeError:
        #  my_object, 'is not iterable'
        return False

def utils_convert_elem_into_array(source: list, destination: list):
    destination[0] = [None for _ in range(len(source))]
    new_iterable = destination[0]
    for index in range(len(source)):
        if isinstance(source[index], (list, tuple)):
            new_iterable[index]=[]
            utils_convert_elem_into_array(source[index], new_iterable[index])
        elif isinstance(source[index], tf.Tensor):
            new_iterable[index] = source[index].numpy()
        else:
            new_iterable[index] = source[index]

def utils_convert_tensor_elem_into_arrays(source: list, destination: list):
    # raise Exception(f'source={source}, len={len(source)}')
    for index in range(len(source)):
        if isinstance(source[index], tf.Tensor):
            destination[index] = source[index].numpy()
        else:
            raise Exception(f'not a Tensor!: {source[index]}')

def utils_convert_elem_into_bytes(target: list):
    for index in range(len(target)):
        target[index] = pickle.dumps(target[index])

def utils_collect_garbage(container_id: str):
    global Global_Tensor_Dict

    items_to_remove = Object_Ownership[container_id]
    for item in items_to_remove:
        del Global_Tensor_Dict[item]
    # try:
    #     del Subdir_Dict[container_id]
    # except KeyError as e:
    #     logging.error(f'KeyError Catched: {e}')

def utils_inference_wrapper(sndpipe, model, args):
    # print('misun:', model, type(args), args)
    ret_val = model(args)
    sndpipe.send(ret_val)
    sndpipe.close()

def utils_infer_target(snd, callable_obj, args):
    obj_name = Global_Model_Dict[callable_obj].model
    ret_val = obj_name(args)
    # ret_val = callable_obj(args)
    snd.send(ret_val)
    return 0

def _get_client_root(container):
    merged_dir = subprocess.check_output('docker inspect -f {{.GraphDriver.Data.MergedDir}} ' + container, shell=True).decode('utf-8').strip()
    logging.info(f'merged_dir={merged_dir}')
    layer_id = merged_dir.split('/')[5]

    return hostroot + layer_id + '/merged'
    

# def utils_add_to_subdir(container_id):
#     subdir = _get_client_root(container_id)
#     Subdir_Dict[container_id] = subdir


# @jit(nopython=True, nogil=True, parallel=True)
# @ray.remote
# @child_process
# def utils_infer(callable_obj, args):
#     return callable_obj(args)

def yolo_boxes(pred, anchors, classes):
    # pred: (batch_size, grid, grid, anchors, (x, y, w, h, obj, ...classes))
    grid_size = tf.shape(pred)[1]
    box_xy, box_wh, objectness, class_probs = tf.split(
        pred, (2, 2, 1, classes), axis=-1)

    box_xy = tf.sigmoid(box_xy)
    objectness = tf.sigmoid(objectness)
    class_probs = tf.sigmoid(class_probs)
    pred_box = tf.concat((box_xy, box_wh), axis=-1)  # original xywh for loss

    # !!! grid[x][y] == (y, x)
    grid = tf.meshgrid(tf.range(grid_size), tf.range(grid_size))
    grid = tf.expand_dims(tf.stack(grid, axis=-1), axis=2)  # [gx, gy, 1, 2]

    box_xy = (box_xy + tf.cast(grid, tf.float32)) / \
        tf.cast(grid_size, tf.float32)
    box_wh = tf.exp(box_wh) * anchors

    box_x1y1 = box_xy - box_wh / 2
    box_x2y2 = box_xy + box_wh / 2
    bbox = tf.concat([box_x1y1, box_x2y2], axis=-1)

    return bbox, objectness, class_probs, pred_box

def yolo_nms(outputs, anchors, masks, classes):
    # boxes, conf, type
    b, c, t = [], [], []

    for o in outputs:
        b.append(tf.reshape(o[0], (tf.shape(o[0])[0], -1, tf.shape(o[0])[-1])))
        c.append(tf.reshape(o[1], (tf.shape(o[1])[0], -1, tf.shape(o[1])[-1])))
        t.append(tf.reshape(o[2], (tf.shape(o[2])[0], -1, tf.shape(o[2])[-1])))

    bbox = tf.concat(b, axis=1)
    confidence = tf.concat(c, axis=1)
    class_probs = tf.concat(t, axis=1)

    scores = confidence * class_probs
    boxes, scores, classes, valid_detections = tf.image.combined_non_max_suppression(
        boxes=tf.reshape(bbox, (tf.shape(bbox)[0], -1, 1, 4)),
        scores=tf.reshape(
            scores, (tf.shape(scores)[0], -1, tf.shape(scores)[-1])),
        max_output_size_per_class=FLAGS.yolo_max_boxes,
        max_total_size=FLAGS.yolo_max_boxes,
        iou_threshold=FLAGS.yolo_iou_threshold,
        score_threshold=FLAGS.yolo_score_threshold
    )

    return boxes, scores, classes, valid_detections

class YoloFunctionWrapper(yolo_pb2_grpc.YoloTensorflowWrapperServicer):
    def ModelBuildingAPI(decoratee_func):
        def decorator_func(self, *args, **kwargs):
            request = args[0]
            if request.container_id != Container_Id:
                logging.info(Color.RED + 'ERROR: Connection ID mismatch!' + Color.END)
                logging.info(f'request.container_id={request.container_id}, container_id={Container_Id}')
                raise IllegalModelBuildException
            else: 
                return self.decoratee_func(*args, **kwargs)
        return decoratee_func

    def Connect(self, request, context):
        global OBJECT_PASS

        logging.info('\nConnect: {request.container_id}')
        response = yolo_pb2.ConnectResponse()

        if request.container_id in Container_Id_Dict:
            response.accept = False
        else:
            response.accept = True
            Container_Id_Dict[request.container_id] = Container_Info(request.container_id, 
                                                    OBJECT_PASS_T(request.object_transfer), 
                                                    _get_client_root(request.container_id))

            # utils_add_to_subdir(request.container_id) # todo : remove
            OBJECT_PASS = OBJECT_PASS_T(request.object_transfer)
            
            logging.info(f'OBJECT_PASS={OBJECT_PASS}')
            # Global_Graph_Dict[request.id] = tf.Graph()
            # Global_Sess_Dict[request.id] = tf.compat.v1.Session(graph=Global_Graph_Dict[request.id])
          
        return response

    def Disconnect(self, request, context):
        logging.info('\nDisconnect: {request.container_id}')
        response = yolo_pb2.DisconnectResponse()

        del Container_Id_Dict[request.container_id]
        # Global_Sess_Dict[request.id].close()
        # del Global_Graph_Dict[request.id]
        # del Global_Sess_Dict[request.id]
        ## todo: global model dict
        threading.Thread(target = utils_collect_garbage, args=[request.container_id]).start()

        return response

    def CheckIfModelExist(self, request, context):
        global Graph_Build_In_Progress, Container_Id

        logging.info('\nCheckIfModelExist')
        response = yolo_pb2.CheckModelExistResponse()

        if request.name in Global_Model_Dict:
            if Global_Model_Dict[request.name].state is ModelInfo.State.BUILD_IN_PROGRESS:
                response.exist = True
                response.model_obj_id = 0
            else:
                response.exist = True
                response.model_obj_id = Global_Model_Dict[request.name].obj_id
        else: # no model, give this connection the lock
            if request.plan_to_make:
                with Model_Create_Lock:
                    Graph_Build_In_Progress = True
                    Container_Id = request.container_id
                    Global_Model_Dict[request.name] = ModelInfo(request.name, request.container_id)
            response.exist = False
            response.model_obj_id = 0
    
        return response

    
    def SayHello(self, request, context):
        return yolo_pb2.HelloReply(message=f'Hello, {request.name}')

    def callable_emulator(self, request, context):
        logging.info('\ncallable_emulator')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():
        # with tf.variable_scope(request.container_id, reuse=True):
        response = yolo_pb2.CallResponse()
        
        callable_obj_id = request.callable_obj_id
        callable_obj = None
        temp_args = []
        del_list = []

        ret_val = []
        ret_val1: int
        ret_val2: int
        ret_val3: int
        ret_val4: int

        for arg in request.obj_ids:
            obj = utils_get_obj(arg.obj_id)
            temp_args.append(obj)
            if arg.release:
                del_list.append(arg.obj_id)

        if len(temp_args) > 1:
            args = temp_args
        else:
            args = temp_args[0]
        
        if request.inference:
            callable_obj = Global_Model_Dict[request.callable_model_name].model
        else:
            callable_obj = utils_get_obj(callable_obj_id)
        logging.info(f'callable={type(callable_obj)}\nname={callable_obj.name}\narg_type={type(args)}')


        if request.inference:
            response.pickled = True
            pre_ret_val = callable_obj(args)
            ret_val = [None for _ in range(len(pre_ret_val))]
            utils_convert_tensor_elem_into_arrays(pre_ret_val, ret_val)
            utils_convert_elem_into_bytes(ret_val)
            for elem in ret_val:
                response.pickled_result.append(elem)
            # raise Exception(f'ret_val={ret_val}, pre_ret_val={pre_ret_val}')
        else:
            response.pickled = False
            if request.num_of_returns == 1:
                if request.inference:
                    ret_val1 = callable_obj(args)
                    # raise Exception(f'ret_val1={ret_val1}')
                else:
                    ret_val1 = callable_obj(args)
                ret_val.append(ret_val1) 
            elif request.num_of_returns == 2:
                ret_val1, ret_val2 = callable_obj(args)
                ret_val.append(ret_val1)
                ret_val.append(ret_val2)
            elif request.num_of_returns == 3:
                ret_val1, ret_val2, ret_val3 = callable_obj(args)
                ret_val.append(ret_val1)
                ret_val.append(ret_val2)
                ret_val.append(ret_val3)
            elif request.num_of_returns == 4:
                ret_val1, ret_val2, ret_val3, ret_val4 = callable_obj(args)
                ret_val.append(ret_val1)
                ret_val.append(ret_val2)
                ret_val.append(ret_val3)
                ret_val.append(ret_val4)
            else:
                logging.info('error!, request.num_of_returns=',request.num_of_returns)
                return None
            for val in ret_val:
                response.obj_ids.append(utils_set_obj(val, request.container_id))
            
        return response

    def get_iterable_slicing(self, request, context):
        logging.info('\nget_iterable_slcing')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():

        response = yolo_pb2.SlicingResponse()

        obj = utils_get_obj(request.iterable_id)
        sliced_obj = obj[request.start:request.end]
        response.obj_id = utils_set_obj(sliced_obj, request.container_id)

        return response

    def config_experimental_list__physical__devices(self, request, context):
        logging.info('\nconfig_experimental_list__physical__devices')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():

        response=yolo_pb2.PhysicalDevices()
        
        tf_physical_devices = tf.config.experimental.list_physical_devices(request.device_type)
        for tf_physical_device in tf_physical_devices:
            physical_device = yolo_pb2.PhysicalDevices.PhysicalDevice()
            physical_device.name = tf_physical_device.name
            physical_device.device_type = tf_physical_device.device_type
            response.devices.append(physical_device)

        return response

    def image_decode__image(self, request, context):
        logging.info('\nimage_decode__image')
        container_id = request.container_id

        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():
        response=yolo_pb2.DecodeImageResponse()

        image_path = ''
        container_info = Container_Id_Dict[container_id]

        if request.data_channel == yolo_pb2.DecodeImageRequest.ObjectTransfer.PATH: 
            if request.path_raw_dir:
                image_path = request.image_path
            else:
                prefix = container_info.subdir
                image_path = prefix + request.image_path
            image_bin = open(image_path, 'rb').read()
        elif request.data_channel == yolo_pb2.DecodeImageRequest.ObjectTransfer.BINARY:
            image_bin = request.bin_image
        elif request.data_channel == yolo_pb2.DecodeImageRequest.ObjectTransfer.SHMEM:
            image_bin = container_info.read(request.shmem_size)
        else:
            raise Exception(f'No such data channel: {request.data_channel}')

        image_raw = tf.image.decode_image(image_bin, channels=request.channels, expand_animations=False)
        obj_id = utils_set_obj(image_raw, request.container_id)
        # print(f'misun: image_raw={image_raw}, obj_id={obj_id}, shape={image_raw.shape}')

        response.obj_id=obj_id
        return response

    def expand__dims(self, request, context):
        logging.info('\nexpand__dims')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():

        response=yolo_pb2.ExpandDemensionResponse()
        image_obj_id = request.obj_id
        image_obj = utils_get_obj(image_obj_id)
        tensor = tf.expand_dims(image_obj, request.axis)
        tensor_obj_id = utils_set_obj(tensor, request.container_id)
        response.obj_id=tensor_obj_id

        return response

    @ModelBuildingAPI
    def keras_Model(self, request, context):
        logging.info('\nkeras_Model')
        _id = request.container_id
    # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():

        response = yolo_pb2.ModelResponse()

        inputs = []
        for id in request.input_ids:
            inputs.append(utils_get_obj(id))
        outputs = []
        for id in request.output_ids:
            outputs.append(utils_get_obj(id))
        name = request.name

        if len(outputs) > 1:
            result = Model(inputs, outputs, name=name)
        else:
            result = Model(inputs, outputs[0], name=name)

        if request.fixed:
            if request.name not in Global_Model_Dict:
                raise IllegalModelBuildException
            else:
                # try:
                #     os.makedirs('tmp')
                # except:
                #     pass
                # # todo remove
                # tf.saved_model.save(result, 'tmp/model')
                # import json
                # json.dumps(result)
                # result.save('tmp/model.h5')
                # exit()
                # # imported = tf.saved_model.load('tmp/model', request.name)
                # imported = tf.keras.models.load_model('tmp/model.h5')
                # Global_Model_Dict[request.name].set_done(imported)
                # import json
                # json.dumps(ret_val)
                # exit()
                Global_Model_Dict[request.name].set_done(result)
        else:
            response.obj_id = utils_set_obj(result, request.container_id)

        return response

    @ModelBuildingAPI
    def keras_layers_Input(self, request, context):
        logging.info('\nkeras_layers_Input')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():

        response = yolo_pb2.InputResponse()
        shape=[]
        for i in request.shape:
            if i is 0:
                shape.append(None)
            else:
                shape.append(i)

        logging.info(shape)
        inputs = Input(shape, name=request.name)

        ## because keras input is not picklable
        response.obj_id = utils_set_obj(inputs, request.container_id)
        return response

    @ModelBuildingAPI
    def keras_layers_ZeroPadding2D(self, request, context):
        global zero_padding2d_count
        zero_padding2d_count += 1
        name = 'zero_padding2d_{:010d}'.format(zero_padding2d_count)
        request.name=name

        logging.info('\nkeras_layers_ZeroPadding2D')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():

        response = yolo_pb2.ZeroPadding2DResponse()
        
        padding = pickle.loads(request.padding)
        data_format = None
        if len(request.data_format) > 0:
            data_format = request.data_format

        zero_padding_2d = ZeroPadding2D(padding, data_format, name=request.name)
        response.obj_id = utils_set_obj(zero_padding_2d, request.container_id)

        return response

    @ModelBuildingAPI
    def keras_layers_Conv2D(self, request, context):
        global conv2d_count
        conv2d_count += 1
        name = 'conv2d_{:010d}'.format(conv2d_count)
        request.name=name

        logging.info('\nkeras_layers_Conv2D')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():

        response = yolo_pb2.Conv2DResponse()

        filters = request.filters
        kernel_size = pickle.loads(request.pickled_kernel_size)
        strides = pickle.loads(request.pickled_strides)
        padding = request.padding
        use_bias = request.use_bias
        if request.pickled_kernel_regularizer is not None:
            kernel_regularizer = pickle.loads(request.pickled_kernel_regularizer)
        else:
            kernel_regularizer = None
        logging.info('type', type(kernel_regularizer))

        conv_2d = Conv2D(filters=filters, kernel_size=kernel_size, strides=strides, padding=padding, use_bias=use_bias, kernel_regularizer=kernel_regularizer, name=request.name)

        response.obj_id = utils_set_obj(conv_2d, request.container_id)
        return response

    @ModelBuildingAPI
    def batch_normalization(self, request, context):
        global batch_norm_count
        batch_norm_count += 1
        name = 'batchnorm_{:010d}'.format(batch_norm_count)
        request.name=name

        logging.info('\nbatch_normalization')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():

        response = yolo_pb2.BatchNormResponse()
        callable_obj = BatchNormalization(name=request.name)

        response.obj_id = utils_set_obj(callable_obj, request.container_id)
        return response

    @ModelBuildingAPI
    def keras_layers_LeakyReLU(self, request, context):
        global leaky_re_lu_count
        leaky_re_lu_count += 1
        name = 'leaky_re_lu_{:010d}'.format(leaky_re_lu_count)
        request.name=name

        logging.info('\nkeras_layers_LeakyReLU')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():
        response = yolo_pb2.LeakyReluResponse()
        alpha = request.alpha

        callable_obj = LeakyReLU(alpha = alpha, name=request.name)
        logging.info(f'leakyreluname={callable_obj.name}')
        response.obj_id = utils_set_obj(callable_obj, request.container_id)

        return response

    @ModelBuildingAPI
    def keras_layers_Add(self, request, context):
        global add_count
        add_count += 1
        name = 'add_{:010d}'.format(add_count)
        request.name=name

        logging.info('\nkeras_layers_Add')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():

        response = yolo_pb2.AddResponse()
        callable_obj = Add(name = request.name)
        response.obj_id = utils_set_obj(callable_obj, request.container_id)

        return response

    def attribute_tensor_shape(self, request, context):
        logging.info('\nattribute_tensor_shape')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():

        response = yolo_pb2.TensorShapeResponse()
        obj = utils_get_obj(request.obj_id)
        start = end = 0

        if request.start == 0:
            start = 0

        if request.end == 0:
            end = len(obj.shape)

        shape = obj.shape[start:end]
        logging.info(shape)
        # response.pickled_shape=pickle.dumps(shape)
        # response.obj_id = utils_set_obj(shape)
        for elem in shape:
            if elem is None:
                response.shape.append(-1)
            else:
                response.shape.append(elem)

        return response

    def attribute_model_load__weights(self, request, context):
        logging.info('\nattribute_model_load__weight')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():

        response = yolo_pb2.LoadWeightsResponse()
        model_info = Global_Model_Dict[request.model_name]
        # checkpoint = model.load_weights(request.weights_path) # check if already weighted
        checkpoint = Global_Model_Dict[model_info.name].load_weights(model_info.model, request.weights_path)
        response.obj_id = utils_set_obj(checkpoint, request.container_id)

        return response

    def attribute_checkpoint_expect__partial(self, request, context):
        logging.info('\attribute_checkpoint_expect__partial')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():

        response = yolo_pb2.ExpectPartialResponse()
        checkpoint = utils_get_obj(request.obj_id)
        checkpoint.expect_partial()
        return response

    @ModelBuildingAPI    
    def keras_layers_Lambda(self, request, context):
        global lambda_count
        lambda_count += 1
        if request.name is None or len(request.name) is 0:
            request.name = 'lambda_{:010d}'.format(lambda_count)

        logging.info('\nkeras_layers_Lambda')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():

        response = yolo_pb2.LambdaResponse()
        lambda_func = lambda x: eval(request.expr)
        # lambda_func = exec(request.expr)
        # print(callable(lambda_func), lambda_func.__name__) ## todo: remove
        # print(type(eval('1+2')), eval('1+2'))
        # import json
        # json_str = json.dumps(exec('1+2'))
        lambda_obj = Lambda(lambda_func, name=request.name)
        # print(callable(lambda_obj), hasattr(lambda_obj,'get_config')) ## todo: remove
        response.obj_id = utils_set_obj(lambda_obj, request.container_id)

        return response

    @ModelBuildingAPI
    def keras_layers_UpSampling2D(self, request, context):
        logging.info('\nkeras_layers_UpSampling2D')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():

        response = yolo_pb2.UpSampling2DResponse()
        callable_obj = UpSampling2D(request.size)
        response.obj_id = utils_set_obj(callable_obj, request.container_id)

        return response

    @ModelBuildingAPI
    def keras_layers_Concatenate(self, request, context):
        logging.info('\nkeras_layers_UpSampling2D')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():

        response = yolo_pb2.ContcatenateResponse()
        callable_obj = Concatenate()
        response.obj_id = utils_set_obj(callable_obj, request.container_id)

        return response

    @ModelBuildingAPI
    def keras_regularizers_l2(self, request, context):
        logging.info('\nkeras_regularizers_l2')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():

        response = yolo_pb2.l2Response()
        l2_value = l2(request.l)
        picked_l2 = pickle.dumps(l2_value)
        response.pickled_l2 = picked_l2

        return response

    def image_resize(self, request, context):
        logging.info('\nimage_resize')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():
        response = yolo_pb2.ImageResizeResponse()
        image_id = request.obj_id
        image = utils_get_obj(image_id)
        size = []
        for elem in request.size:
            size.append(elem)
        
        tensor = tf.image.resize(image, size)
        response.obj_id = utils_set_obj(tensor, request.container_id)

        return response

    def tensor_op_divide(self, request, context):
        logging.info('\ntensor_op_divide')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():

        response = yolo_pb2.DivideResponse()
        tensor_obj = utils_get_obj(request.obj_id)
        divisor = request.divisor

        result = tensor_obj / divisor
        response.obj_id = utils_set_obj(result, request.container_id)
        return response

    # to-do: This function is not used anymore, please remove
    def iterable_indexing(self, request, context):
        logging.info('\niterable_indexing')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():

        response = yolo_pb2.IndexingResponse()
        iterable = utils_get_obj(request.obj_id)
        indices = []

        ref_val = iterable[request.indices[0]]

        for index in request.indices[1:]:
            ref_val = ref_val[index]

        logging.info(ref_val)
        # raise Exception(f'ref_val={ref_val}')
        try:
            if len(ref_val) > 0:
                new_ref_val = [[]]
                utils_convert_elem_into_array(ref_val, new_ref_val)
                response.pickled_result = pickle.dumps(new_ref_val[0])
        except TypeError:
            response.pickled_result = pickle.dumps(ref_val.eval())

        return response

    def byte_tensor_to_numpy(self, request, context):
        logging.info('\nbyte_tensor_to_numpy')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():

        response = yolo_pb2.TensorToNumPyResponse()

        tensor = utils_get_obj(request.obj_id)
        array = tensor.numpy()
        container_info = Container_Id_Dict[_id]

        pickled_array = pickle.dumps(array)
        response.data_length = len(pickled_array)
        
        if container_info.object_pass == OBJECT_PASS_T.SHMEM:
            container_info.shmem.write(pickled_array)
        else:
            response.pickled_array = pickled_array

        return response

    def get_object_by_id(self, request, context):
        logging.info('\nget_object_by_id')
        _id = request.container_id
        # with Global_Sess_Dict[_id].as_default(), tf.name_scope(_id), Global_Graph_Dict[_id].as_default():

        response = yolo_pb2.GetObjectResponse()

        _object = utils_get_obj(request.obj_id)
        response.object = pickle.dumps(_object)

        return response

def make_json(container_id):
    import json
    args_dict = {}

    args_dict['type']='closed-proc-ns'
    args_dict['cid']=container_id
    args_dict['events']=['cpu-cycles','page-faults','minor-faults','major-faults','cache-misses','LLC-load-misses','LLC-store-misses','dTLB-load-misses','iTLB-load-misses','instructions']

    args_json = json.dumps(args_dict)

    return args_json

def connect_to_perf_server(container_id: str):
    logging.info('connect_to_perf_server')
    my_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    my_socket.connect(PERF_SERVER_SOCKET)
    json_data_to_send = make_json(container_id)
    my_socket.sendall(json_data_to_send.encode('utf-8'))
    data_received = my_socket.recv(1024)
    logging.info(f'data_received={data_received}')
    my_socket.close()

def offline_init():
    physical_devices = tf.config.experimental.list_physical_devices('GPU')
    if len(physical_devices) > 0: # in my settings, this if statement always returns false
        tf.config.experimental.set_memory_growth(physical_devices[0], True)
    yolo = YoloV3(classes=FLAGS.num_classes)
    yolo.load_weights(FLAGS.weights).expect_partial()
    # class_names = [c.strip() for c in open(FLAGS.classes).readlines()]

    with Model_Create_Lock:
        Global_Model_Dict['yolov3'] = ModelInfo('yolov3', 'server')
        Global_Model_Dict['yolov3'].set_done(yolo)


def serve():
    # offline_init()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=47), options=[('grpc.so_reuseport', 1), ('grpc.max_send_message_length', -1), ('grpc.max_receive_message_length', -1)])
    yolo_pb2_grpc.add_YoloTensorflowWrapperServicer_to_server(YoloFunctionWrapper(), server)
    server.add_insecure_port('[::]:1990')
    physical_devices = tf.config.experimental.get_visible_devices('CPU')
    # tf.config.threading.set_inter_op_parallelism_threads(48)
    # tf.config.threading.set_intra_op_parallelism_threads(96)
    server.start()
    # connect_to_perf_server(socket.gethostname())

    server.wait_for_termination()

def finalize(signum, frame):
    # if 'cProfile' in dir():
    #     cProfile.create_stats()
    sys.exit(0)

from pocketmgr import PocketManager
if __name__ == '__main__':
    FLAGS(sys.argv)
    signal.signal(signal.SIGINT, finalize)

    # mgr = PocketManager()
    # mgr.start()
    # exit()

    # msgq = MessageQueue(universal_key, IPC_CREX)
    # data, type = msgq.receive()
    # print(data)
    # if type == 0x1:
    #     reply_type = type | 0x40000000
    #     print(reply_type)
    #     msgq.send(data, type = reply_type)

    # exit()
    logging.basicConfig()
    FLAGS(sys.argv)
    # print(f'hostroot={hostroot}')
    subprocess.check_call(f'mkdir -p {hostroot}', shell=True)
    time.sleep(3)
    serve()