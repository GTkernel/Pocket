from enum import IntEnum, Enum
import os
from sysv_ipc import SharedMemory, Semaphore, IPC_CREX
# self.value, self.name

CLIENT_TO_SERVER = 0x1
SERVER_TO_CLIENT = 0x2
POCKET_CLIENT = False

if os.environ.get('POCKET_CLIENT', 'False') == 'True':
    POCKET_CLIENT = True


def debug(*args):
    import inspect
    filename = inspect.stack()[1].filename
    lineno = inspect.stack()[1].lineno
    caller = inspect.stack()[1].function
    print(f'debug>> [{filename}:{lineno}, {caller}]', *args)

class SharedMemoryChannel:
    # [0: 32) Bytes: header
    ### [0, 4) Bytes: size
    # [32, -] Bytes: data
    def __init__(self, key, size=None, path=None):
        self.key = int(key[:8], 16)
        import time
        if POCKET_CLIENT:
            # debug('here!!!', time.time(), self.key, type(self.key))
            self.shmem = SharedMemory(self.key , IPC_CREX, size=size)
            self.sem = Semaphore(self.key , IPC_CREX, initial_value = 1)
            
        else:
            # debug('there!!!', time.time(), self.key, type(self.key))
            self.shmem = SharedMemory(self.key)
            self.sem = Semaphore(self.key)

        self.mv = memoryview(self.shmem)

        if path is not None:
            self.write(uri=path)

    def write(self, uri=None, contents=None, offset = 32):
        if uri is None and contents is None:
            raise Exception('Either uri or contents need to be provided!')
        elif uri is not None and contents is not None:
            raise Exception('Either uri or contents need to be provided!')

        if uri is not None:
            buf = open(uri, 'rb').read()
        elif contents is not None:
            buf = contents

        length = len(buf)
        self.sem.acquire()
        self.mv[0:4] = length.to_bytes(4, 'little')
        self.mv[32:32+length] = buf
        # print(self.mv[32:], type(buf))
        self.sem.release()

    def read(self, size=None):
        self.sem.acquire()
        length = self.mv[0:4]
        data = self.mv[32:32+size]
        self.sem.release()
        return data

    def view(self, size=None):
        self.sem.acquire()
        self.mv = memoryview(self.shmem)
        self.sem.release()
        return self.mv[:size]

    def finalize(self):
        self.sem.remove()
        self.shmem.detach()
        self.shmem.remove()

class PocketControl(IntEnum):
    CONNECT = 0x1
    DISCONNECT = 0x2
    HELLO = 0x3
    START_BUILD_GRAPH = 0x4
    END_BUILD_GRAPH = 0x5
    

class TFFunctions(IntEnum):
    LOCALQ_DEBUG = 0x00000001
    MODEL_EXIST = 0x00000002
    TF_CALLABLE = 0x00000003
    OBJECT_SLICER = 0x00000004
    TF_SHAPE = 0x00000005
    TF_RESHAPE = 0x00000006
    TENSOR_DIVISION = 0x00000007
    # TENSOR_SHAPE = 0x00000008
    TF_CONSTANT = 0x00000009
    TF_SIGMOID = 0x0000000a

    _NOPTEST = 0x00001001
    _MATMULTEST = 0x00001002

    TF_CONFIG_EXPERIMENTAL_LIST__PHYSICAL__DEVICES = 0x10000001
    TF_CONFIG_EXPERIMENTAL_SET__MEMORY__GROWTH = 0x10000002
    TF_GRAPH_GET__TENSOR__BY__NAME = 0x10000003
    TF_KERAS_LAYERS_INPUT = 0x10000004
    TF_KERAS_LAYERS_ZEROPADDING2D = 0x10000005
    TF_KERAS_REGULARIZERS_L2 = 0x10000006
    TF_KERAS_LAYERS_CONV2D = 0x10000007
    TF_KERAS_LAYERS_BATCHNORMALIZATION = 0x10000008
    TF_KERAS_LAYERS_LEAKYRELU = 0x10000009
    TF_KERAS_LAYERS_ADD = 0x1000000a
    TF_KERAS_MODEL = 0x1000000b
    TF_KERAS_LAYERS_LAMBDA = 0x1000000c
    TF_KERAS_LAYERS_UPSAMPLING2D = 0x1000000d
    TF_KERAS_LAYERS_CONCATENATE = 0x1000000e
    TF_IMAGE_DECODE__IMAGE = 0x1000000f
    TF_EXPAND__DIMS = 0x10000010
    TF_IMAGE_RESIZE = 0x10000011
    TF_KERAS_APPLICATIONS_MOBILENETV2 = 0x10000012
    TF_KERAS_APPLICATIONS_RESNET50 = 0x10000013
    TF_KERAS_PREPROCESSING_IMAGE_IMG__TO__ARRAY = 0x10000014
    TF_KERAS_APPLICATIONS_RESNET50_PREPROCESS__INPUT = 0x10000015
    TF_SAVED__MODEL_LOAD = 0x10000016

    TF_MODEL_LOAD_WEIGHTS = 0x20000001
    HUB_LOAD = 0x20000002

    NP_ARGMAX = 0x30000001



class TFDtypes(Enum):
    tf_dtypes_float16 = 'tf.dtypes.float16'
    tf_dtypes_float32 = 'tf.dtypes.float32'
    tf_dtypes_float64 = 'tf.dtypes.float64'
    tf_dtypes_bfloat16 = 'tf.dtypes.bfloat16'
    tf_dtypes_complex64 = 'tf.dtypes.complex64'
    tf_dtypes_complex128 = 'tf.dtypes.complex128'
    tf_dtypes_int8 = 'tf.dtypes.int8'
    tf_dtypes_uint8 = 'tf.dtypes.uint8'
    tf_dtypes_uint16 = 'tf.dtypes.uint16'
    tf_dtypes_uint32 = 'tf.dtypes.uint32'
    tf_dtypes_uint64 = 'tf.dtypes.uint64'
    tf_dtypes_int16 = 'tf.dtypes.int16'
    tf_dtypes_int32 = 'tf.dtypes.int32'
    tf_dtypes_int64 = 'tf.dtypes.int64'
    tf_dtypes_bool = 'tf.dtypes.bool'
    tf_dtypes_string = 'tf.dtypes.string'
    tf_dtypes_qint8 = 'tf.dtypes.qint8'
    tf_dtypes_quint8 = 'tf.dtypes.quint8'
    tf_dtypes_qint16 = 'tf.dtypes.qint16'
    tf_dtypes_quint16 = 'tf.dtypes.quint16'
    tf_dtypes_qint32 = 'tf.dtypes.qint32'
    tf_dtypes_resource = 'tf.dtypes.resource'
    tf_dtypes_variant = 'tf.dtypes.variant'

class ResizeMethod(Enum):
    AREA = 'area'
    BICUBIC = 'bicubic'
    BILINEAR = 'bilinear'
    GAUSSIAN = 'gaussian'
    LANCZOS3 = 'lanczos3'
    LANCZOS5 = 'lanczos5'
    MITCHELLCUBIC = 'mitchellcubic'
    NEAREST_NEIGHBOR = 'nearest'

class ReturnValue(IntEnum):
    OK = 0
    ERROR = 1
    EXCEPTIONRAISED = 2

def empty_function():
    raise Exception('Not Implemented, empty function!')

class TFDataType:
    callable_delegator = empty_function
    iterable_slicer = empty_function

    class PhysicalDevice:
        def __init__ (self, name = None, device_type = None, dict = None):
            if dict == None:
                self._typename = 'tf.config.PhysicalDevice'
                self.name = name
                self.device_type = device_type
                self.obj_id = None
            else:
                for key, value in dict.items():
                    self.__setattr__(key, value)

        def to_dict(self):
            return self.__dict__

    # class TensorShape:
    #     def __init__(self, tensor_id = None, dict = None):
    #         self._typename = 'tf.TensorShape'
    #         self.tensor_id = tensor_id
        
    #     def __getitem__(self, key):
    #         if POCKET_CLIENT is True:
    #             debug(f'key={key} id={self.tensor_id}')
    #             ret = TFDataType.iterable_slicer(self.to_dict(), key)
    #             return ret
    #         else:
    #             raise Exception('Only client can call this!')

    class Tensor:
        tensor_division = empty_function
        get_shape = empty_function

        @classmethod
        def make_tensor(cls, dict):
            if 'value' in dict and dict['value'] is not None:
                return dict['value']
            else:
                return cls(dict=dict)

        def __init__ (self, name = None, obj_id = None, shape=None, tensor=None, dict = None):
            if dict == None:
                self._typename = 'tf.Tensor'
                self.name = name
                self.obj_id = obj_id
                self.shape = shape
                if tensor is not None:
                    try:
                        self.value = tensor.numpy().item()
                    except ValueError as e:
                        tensor = None
            else:
                for key, value in dict.items():
                    # self.__setattr__(key, value)
                    self.__dict__[key] = value

        def set_value(self, value):
            self.value = value

        def __int__(self):
            return self.value

        def to_dict(self):
            return self.__dict__
            
        def __call__(self, *args, infer=False):
            if POCKET_CLIENT is True:
                ret = TFDataType.callable_delegator(self._typename, self.to_dict(), *args)
                return ret
            else:
                raise Exception('Only client can call this!')

        def __getitem__(self, key):
            if POCKET_CLIENT is True:
                # debug(f'key={key} name={self.name}, id={self.obj_id}')
                ret = TFDataType.iterable_slicer(self.to_dict(), key)
                return ret
            else:
                raise Exception('Only client can call this!')
        
        def __truediv__(self, other):
        # def __div__(self, other):
            if POCKET_CLIENT is True:
                ret = TFDataType.Tensor.tensor_division(self.to_dict(), other)
                return ret
            else:
                raise Exception('Only client can call this!')

        # @property
        # def shape(self):
        #     if self._shape is not None:
        #         return self._shape
        #     else:
        #         ret = TFDataType.Tensor.get_shape(self.to_dict())
        #         self._shape = ret
        #         return ret



    class Model(Tensor):
        load_weights = empty_function
        def __init__ (self, name = None, obj_id = None, already_built=False, dict = None):
            if dict == None:
                self._typename = 'tf.keras.Model'
                self.name = name
                self.obj_id = obj_id
                self.already_built=already_built
            else:
                for key, value in dict.items():
                    self.__setattr__(key, value)

        def load_weights(self, filepath, by_name=False, skip_mismatch=False):
            if POCKET_CLIENT is True:
                if self.already_built is False:
                    TFDataType.Model.load_weights(self, filepath, by_name=False, skip_mismatch=False)
                else:
                    pass
            else:
                raise Exception('Only client can call this!')


    class ZeroPadding2D(Tensor):
        def __init__ (self, name = None, obj_id = None, dict = None):
            if dict == None:
                self._typename = 'tf.keras.layers.ZeroPadding2D'
                self.name = name
                self.obj_id = obj_id
            else:
                for key, value in dict.items():
                    self.__setattr__(key, value)

    class L2(Tensor):
        def __init__ (self, obj_id = None, dict = None):
            if dict == None:
                self._typename = 'tf.keras.regularizers.L2'
                self.obj_id = obj_id
            else:
                for key, value in dict.items():
                    self.__setattr__(key, value)


    class Conv2D(Tensor):
        def __init__ (self, name = None, obj_id = None, dict = None):
            if dict == None:
                self._typename = 'tf.keras.layers.Conv2D'
                self.name = name
                self.obj_id = obj_id
            else:
                for key, value in dict.items():
                    self.__setattr__(key, value)

    class BatchNormalization(Tensor):
        def __init__ (self, name = None, obj_id = None, shape=None, dict = None):
            if dict == None:
                self._typename = 'tf.keras.layers.BatchNormalization'
                self.name = name
                self.obj_id = obj_id
                self.shape = shape
            else:
                for key, value in dict.items():
                    self.__setattr__(key, value)

    class LeakyReLU(Tensor):
        def __init__ (self, name = None, obj_id = None, dict = None):
            if dict == None:
                self._typename = 'tf.keras.layers.LeakyReLU'
                self.name = name
                self.obj_id = obj_id
            else:
                for key, value in dict.items():
                    self.__setattr__(key, value)

    class Add(Tensor):
        def __init__ (self, name = None, obj_id = None, dict = None):
            if dict == None:
                self._typename = 'tf.keras.layers.Add'
                self.name = name
                self.obj_id = obj_id
            else:
                for key, value in dict.items():
                    self.__setattr__(key, value)

    class Lambda(Tensor):
        def __init__ (self, name = None, obj_id = None, dict = None):
            if dict == None:
                self._typename = 'tf.keras.layers.Add'
                self.name = name
                self.obj_id = obj_id
            else:
                for key, value in dict.items():
                    self.__setattr__(key, value)
        # def __init__ (self, function = None, output_shape=None, mask=None, arguments=None, **kwargs):
        #     self._typename = 'tf.keras.layers.Lambda'
        #     self.function = function
        #     self.output_shape = output_shape
        #     self.mask = mask
        #     self.arguments = arguments

        # def __call__ (self, input)


    class UpSampling2D(Tensor):
        def __init__ (self, name = None, obj_id = None, dict = None):
            if dict == None:
                self._typename = 'tf.keras.layers.Add'
                self.name = name
                self.obj_id = obj_id
            else:
                for key, value in dict.items():
                    self.__setattr__(key, value)


    class Concatenate(Tensor):
        def __init__ (self, name = None, obj_id = None, dict = None):
            if dict == None:
                self._typename = 'tf.keras.layers.Add'
                self.name = name
                self.obj_id = obj_id
            else:
                for key, value in dict.items():
                    self.__setattr__(key, value)

class NPArray:
    def __init__ (self, shape, length, dtype = 'uint8', dict=None):
        if dict == None:
            self._typename = 'NPArray'
            self.shape = shape
            self.dtype = dtype
            self.contents_length = length
        else:
            for key, value in dict.items():
                self.__setattr__(key, value)
