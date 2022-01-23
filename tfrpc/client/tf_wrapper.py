import os
import yolo_pb2
import yolo_pb2_grpc
import pickle
import string, random
import subprocess

# Status:
#     - Done: detect.py
#     - In-Progress: models.py, utils.py
#     - Undone: dataset.py, batch_norm.py,

# conv2d_count = 0
# batch_norm_count = 0
# leaky_re_lu_count = 0
# zero_padding2d_count=0
# add_count = 0
# lambda_count = 0

def utils_random_string(size = 12, chars = string.ascii_lowercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))

def is_ramfs(path: str):
    try:
        return os.path.samefile(os.path.dirname(os.path.normpath(path)), '/ramfs')
    except FileNotFoundError:
        return False

def is_img_storage(path: str):
    try:
        return os.path.samefile(os.path.dirname(os.path.normpath(path)), '/images')
    except FileNotFoundError:
        return False

    # todo: shmem align, global variables...

class ControlProcedure:
    # container_id = subprocess.check_output('cat /proc/self/cgroup | grep cpuset | cut -d/ -f3 | head -1', shell=True, encoding='utf-8').strip()
    container_id = ''
    shmem_channel =  ''
    data_channel = ''

    # print(f'container_id={container_id}')
    @staticmethod
    def Connect(stub, obj_pass: str, container_id, shmem_channel=None): # path, bin, redis
        request = yolo_pb2.ConnectRequest()
        response: yolo_pb2.ConnectResponse

        ControlProcedure.container_id = container_id
        request.container_id = ControlProcedure.container_id

        ControlProcedure.data_channel = obj_pass

        if obj_pass == 'bin':
            request.object_transfer = yolo_pb2.ConnectRequest.ObjectTransfer.BINARY
            ControlProcedure.data_channel = 'bin'
        elif obj_pass == 'path':
            request.object_transfer = yolo_pb2.ConnectRequest.ObjectTransfer.PATH
            ControlProcedure.data_channel = 'path'
        elif obj_pass == 'redis':
            request.object_transfer = yolo_pb2.ConnectRequest.ObjectTransfer.REDIS_OBJ_ID
            ControlProcedure.data_channel = 'redis'
        elif obj_pass == 'shmem':
            request.object_transfer = yolo_pb2.ConnectRequest.ObjectTransfer.SHMEM
            ControlProcedure.shmem_channel = shmem_channel
            ControlProcedure.data_channel = 'shmem'
        while True:
            request.id = utils_random_string()
            response = stub.Connect(request)
            if response.accept:
                ControlProcedure.client_id = request.id
                break

    @staticmethod
    def Disconnect(stub):
        request = yolo_pb2.DisconnectRequest()
        response: yolo_pb2.DisconnectResponse

        request.container_id = ControlProcedure.container_id
        response = stub.Disconnect(request)

    @staticmethod
    def SayHello(stub, name):
        request = yolo_pb2.HelloRequest()
        response: yolo_pb2.HelloReply

        request.name = name
        response = stub.SayHello(request)
        print(response.message)
        return True

class gRPCTest:
    @staticmethod
    def SendImageViaPath(stub, path: str):
        pass

    @staticmethod
    def SendImageBinary(stub, image: bytes):
        pass

    @staticmethod
    def SendInteger(stub, num: int):
        pass


class TFWrapper:
    @staticmethod
    def callable_emulator(stub, callable_obj_id, inference, ret_num, model_name, *argv):
        request = yolo_pb2.CallRequest()
        response: yolo_pb2.CallResponse

        request.callable_obj_id = callable_obj_id
        request.num_of_returns = ret_num
        request.container_id = ControlProcedure.container_id
        request.inference=inference
        request.callable_model_name = model_name

        # if args_picklable:
        #     request.args_pickled = True
        #     for arg in argv:
        #         request.pickled_args.append(arg)
        # else:
        # request.args_pickled = False
        for arg in argv:
            request.obj_ids.append(arg)

        response = stub.callable_emulator(request)

        if response.pickled:
            serialized_result = []
            for elem in response.pickled_result:
                serialized_result.append(pickle.loads(elem))
            return serialized_result
        else:
            if len(response.obj_ids) > 1:
                return response.obj_ids
            else:
                return response.obj_ids[0]

            if ret_num == 1:
                return response.obj_ids[0]
            elif ret_num == 2:
                return response.obj_ids[0], response.obj_ids[1]
            elif ret_num == 3:
                return response.obj_ids[0], response.obj_ids[1], response.obj_ids[2]
            elif ret_num == 4:
                return response.obj_ids[0], response.obj_ids[1], response.obj_ids[2], response.obj_ids[3]
            else:
                print('error!')
                exit()

    @staticmethod
    def get_iterable_slicing(stub, iterable, start, end):
        request = yolo_pb2.SlicingRequest()
        response: yolo_pb2.SlicingResponse

        request.iterable_id = iterable
        request.start = start
        request.end = end
        request.container_id = ControlProcedure.container_id

        response = stub.get_iterable_slicing(request)
        return response.obj_id

    @staticmethod
    def tf_constant(stub, value):
        request = yolo_pb2.ConstantRequest()
        response: yolo_pb2.ConstantResponse

        request.value = pickle.dumps(value)
        request.container_id = ControlProcedure.container_id

        response = stub.constant(request)

        # unpickled_result = pickle.loads(response.tensor)
        # return unpickled_result
        return response.tensor

    @staticmethod
    def tf_config_experimental_list__physical__devices(stub, device_type=None):
        # tf.config.experimental.list_physical_devices('GPU')
        request=yolo_pb2.DeviceType()
        response: yolo_pb2.PhysicalDevices

        request.device_type = device_type
        request.container_id = ControlProcedure.container_id

        response = stub.config_experimental_list__physical__devices(request)

        return response.devices
        
    @staticmethod
    def config_experimental_set__memory__growth(stub, physical_device, bool):
        print('Error! not implemented')
        return None
    
    @staticmethod
    def tf_image_decode__image(stub, channels=None, 
                                image_path=None, 
                                data_channel = None, data_size_in_byte = None,
                                data_bytes = None, shmem = None):
        # img_raw = tf.image.decode_image(open(FLAGS.image, 'rb').read(), channels=3)
        request = yolo_pb2.DecodeImageRequest()
        response: yolo_pb2.DecodeImageResponse

        request.channels=channels
        if data_channel == 'path':
            if is_ramfs(image_path) or is_img_storage(image_path): # ramfs dir (shared), # regular storage dir (shared)
                request.data_channel = yolo_pb2.DecodeImageRequest.ObjectTransfer.PATH
                request.path_raw_dir = True
                request.image_path = image_path
            else:
                request.data_channel = yolo_pb2.DecodeImageRequest.ObjectTransfer.PATH
                request.path_raw_dir = False
                request.image_path = os.path.abspath(image_path)
        elif data_channel == 'shmem':
            request.data_channel = yolo_pb2.DecodeImageRequest.ObjectTransfer.SHMEM
            request.shmem_size = data_size_in_byte
            # shmem.write(image_path)
        elif data_channel == 'bin':
            request.data_channel = yolo_pb2.DecodeImageRequest.ObjectTransfer.BINARY

            request.bin_image = data_bytes
        elif data_channel == 'redis':
            request.data_channel = yolo_pb2.DecodeImageRequest.ObjectTransfer.REDIS_OBJ_ID
            raise Exception('Not Implemented Yet')
        else:
            raise Exception('Unknow data channel!')

        request.container_id = ControlProcedure.container_id

        response = stub.image_decode__image(request)
        # unpickled_tensor = pickle.loads(response.tensor)
        # return unpickled_tensor
        return response.obj_id

    @staticmethod
    def tf_expand__dims(stub, input, axis):
        # img = tf.expand_dims(img_raw, 0)
        request = yolo_pb2.ExpandDemensionRequest()
        response: yolo_pb2.ExpandDemensionResponse

        request.obj_id=input
        request.axis=axis
        request.container_id = ControlProcedure.container_id

        response = stub.expand__dims(request) 
        # unpickled_tensor = pickle.loads(response.tensor)
        # return unpickled_tensor
        return response.obj_id

    @staticmethod
    def tf_keras_layers_Input(stub, shape: tuple, name: str = None):
        # x = inputs = Input([size, size, channels], name='input')
        request = yolo_pb2.InputRequest()
        response: yolo_pb2.InputResponse

        for i in shape:
            if i is None:
                request.shape.append(0)
            else:
                request.shape.append(i)
        
        if name is not None:
            request.name = name
        request.container_id = ControlProcedure.container_id

        response = stub.keras_layers_Input(request)
        input_id = response.obj_id
        return input_id

    @staticmethod
    def tf_keras_Model(stub, inputs, outputs, name: str, fixed=False):
        # tf.keras.Model(inputs, (output_0, output_1, output_2), name='yolov3')
        request = yolo_pb2.ModelRequest()
        response: yolo_pb2.ModelResponse()

        for elem in inputs:
            request.input_ids.append(elem)

        for elem in outputs:
            request.output_ids.append(elem)
        request.name = name
        request.container_id = ControlProcedure.container_id
        request.fixed = fixed

        response = stub.keras_Model(request)

        return response.obj_id

    @staticmethod
    def tf_keras_layers_ZeroPadding2D(stub, padding=(1, 1), data_format=None):
        # global zero_padding2d_count
        # zero_padding2d_count += 1
        # name = 'zero_padding2d_{:010d}'.format(zero_padding2d_count)

        request = yolo_pb2.ZeroPadding2DRequest()
        response: yolo_pb2.ZeroPadding2DResponse

        request.container_id = ControlProcedure.container_id
        request.padding = pickle.dumps(padding)
        # request.name = name
        if data_format is not None:
            request.data_format=data_format

        response = stub.keras_layers_ZeroPadding2D(request)

        return response.obj_id

    @staticmethod
    def tf_keras_layers_Conv2D(stub, filters: int, kernel_size, strides=(1, 1), padding='valid', use_bias=True, kernel_regularizer=None):
        # global conv2d_count
        # conv2d_count += 1
        # name = 'conv2d_{:010d}'.format(conv2d_count)

        request = yolo_pb2.Conv2DRequest()
        response: yolo_pb2.Conv2DResponse

        # request.name = name
        request.filters = filters
        request.pickled_kernel_size = pickle.dumps(kernel_size)
        request.pickled_strides = pickle.dumps(strides)
        request.padding = padding
        request.use_bias = use_bias

        request.pickled_kernel_regularizer=kernel_regularizer
        request.container_id = ControlProcedure.container_id

        response = stub.keras_layers_Conv2D(request)

        return response.obj_id


    @staticmethod
    def tf_keras_layers_LeakyReLU(stub, alpha):
        # global leaky_re_lu_count
        # leaky_re_lu_count += 1
        # name = 'leaky_re_lu_{:010d}'.format(leaky_re_lu_count)

        request = yolo_pb2.LeakyReluRequest()
        response: yolo_pb2.LeakyReluResponse

        # request.name = name
        request.alpha = alpha
        request.container_id = ControlProcedure.container_id

        response = stub.keras_layers_LeakyReLU(request)

        return response.obj_id

    @staticmethod
    def tf_keras_layers_Add(stub):
        # global add_count
        # add_count += 1
        # name = 'add_{:010d}'.format(add_count)
        
        request = yolo_pb2.AddRequest()
        response: yolo_pb2.AddResponse

        # request.name = name
        request.container_id = ControlProcedure.container_id

        response = stub.keras_layers_Add(request)

        return response.obj_id


    @staticmethod
    def attribute_tensor_shape(stub, target, start=0, end=0):
        request = yolo_pb2.TensorShapeRequest()
        response: yolo_pb2.TensorShapeResponse

        request.obj_id = target[0]
        request.start = start
        request.end = end
        request.container_id = ControlProcedure.container_id

        response = stub.attribute_tensor_shape(request)
        # unpickled_result = pickle.loads(response.pickled_shape)
        temp_list=[]
        for elem in response.shape:
            if elem is -1:
                temp_list.append(None)
            else:
                temp_list.append(elem)

        return tuple(temp_list)

    @staticmethod
    def attribute_model_load__weights(stub, model_name, weights_path: str):
        request = yolo_pb2.LoadWeightsRequest()
        response: yolo_pb2.LoadWeightsResponse

        request.weights_path = weights_path
        request.model_name = model_name
        request.container_id = ControlProcedure.container_id

        response = stub.attribute_model_load__weights(request)
        return response.obj_id

    @staticmethod
    def attribute_checkpoint_expect__partial(stub, checkpoint_obj_id):
        request = yolo_pb2.ExpectPartialRequest()
        response: yolo_pb2.ExpectPartialResponse

        request.obj_id = checkpoint_obj_id
        request.container_id = ControlProcedure.container_id

        response = stub.attribute_checkpoint_expect__partial(request)
        return 

    @staticmethod
    def tensor_op_divide(stub, tensor_obj_id, divisor):
        request = yolo_pb2.DivideRequest()
        response: yolo_pb2.DivideResponse
        ##

        request.obj_id = tensor_obj_id
        request.divisor = divisor
        request.container_id = ControlProcedure.container_id

        response = stub.tensor_op_divide(request)
        return response.obj_id




    @staticmethod
    def tf_keras_layers_Lambda(stub, lambda_str: str, name=None):
        # global lambda_count
        # lambda_count += 1
        # if name is None:
        #     name = 'lambda_{:010d}'.format(lambda_count)

        request = yolo_pb2.LambdaRequest()
        response: yolo_pb2.LambdaResponse

        request.expr = lambda_str
        request.container_id = ControlProcedure.container_id

        # if name is not None:
        #     request.name = name

        if name is None:
            request.name = ''
        else:
            request.name = name

        response = stub.keras_layers_Lambda(request)

        return response.obj_id

    @staticmethod
    def tf_keras_layers_UpSampling2D(stub, size):
        request = yolo_pb2.UpSampling2DRequest()
        response: yolo_pb2.UpSampling2DResponse
        
        request.size = size
        request.container_id = ControlProcedure.container_id

        response = stub.keras_layers_UpSampling2D(request)
        return response.obj_id

    @staticmethod
    def tf_keras_layers_Concatenate(stub):
        request = yolo_pb2.ConcatenateRequest()
        response: yolo_pb2.ContcatenateResponse

        request.container_id = ControlProcedure.container_id
        
        response = stub.keras_layers_Concatenate(request)
        return response.obj_id

    @staticmethod
    def tf_image_resize(stub, image_id, size):
        request = yolo_pb2.ImageResizeRequest()
        response: yolo_pb2.ImageResizeResponse

        request.obj_id = image_id
        request.container_id = ControlProcedure.container_id

        for elem in size:
            request.size.append(elem)

        response = stub.image_resize(request)
        return response.obj_id

    @staticmethod
    def tf_keras_regularizers_l2(stub, l=0.01):
        request = yolo_pb2.l2Request()
        response: yolo_pb2.l2Response

        request.l=l
        request.container_id = ControlProcedure.container_id

        response = stub.keras_regularizers_l2(request)
        # unpickled_l2 = pickle.loads(response.pickled_l2)
        # return unpickled_l2
        return response.pickled_l2

    @staticmethod
    def iterable_indexing(stub, iterable, *args):
        request = yolo_pb2.IndexingRequest()
        response: yolo_pb2.IndexingResponse

        request.obj_id = iterable
        for index in args:
            request.indices.append(index)
        request.container_id = ControlProcedure.container_id

        response = stub.iterable_indexing(request)
        result = pickle.loads(response.pickled_result)

        return result

    @staticmethod
    #Todo
    def byte_tensor_to_numpy(stub, image_obj_id):
        request = yolo_pb2.TensorToNumpyRequest()
        response: yolo_pb2.TensorToNumPyResponse

        request.obj_id = image_obj_id
        request.container_id = ControlProcedure.container_id

        response = stub.byte_tensor_to_numpy(request)
        if ControlProcedure.data_channel == 'shmem':
            return pickle.loads(ControlProcedure.shmem_channel.view(response.data_length))
        else:
            return pickle.loads(response.pickled_array)

    @staticmethod
    def get_object_by_id(stub, obj_id):
        request = yolo_pb2.GetObjectRequest()
        response: yolo_pb2.GetObjectResponse

        request.obj_id = obj_id
        request.container_id = ControlProcedure.container_id

        response = stub.get_object_by_id(request)

        return pickle.loads(response.object)



class YoloWrapper:
    @staticmethod
    def CheckIfModelExist(stub, name, plan_to_make=False):
        request = yolo_pb2.CheckModelExistRequest()
        response: yolo_pb2.CheckModelExistResponse

        request.container_id = ControlProcedure.container_id
        request.name = name
        request.plan_to_make=plan_to_make

        response = stub.CheckIfModelExist(request)
        return response.exist, response.model_obj_id

    @staticmethod
    def BatchNormalization(stub):
        # global batch_norm_count
        # batch_norm_count += 1
        # name = 'batchnorm_{:010d}'.format(batch_norm_count)

        request = yolo_pb2.BatchNormRequest()
        response: yolo_pb2.BatchNormResponse

        # request.name = name
        request.container_id = ControlProcedure.container_id

        response = stub.batch_normalization(request)
        return response.obj_id
