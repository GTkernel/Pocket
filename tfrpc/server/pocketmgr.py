import subprocess
import sys, os
import gc
import json
import tensorflow as tf
import numpy as np
from absl import flags
from absl.flags import FLAGS
from enum import Enum
from queue import Queue
import math
from math import ceil
from ctypes import c_void_p, byref, CDLL, cast, POINTER, c_char, c_size_t, c_int
from ctypes.util import find_library
from imghdr import what
import tensorflow_text

from time import sleep, time
from sysv_ipc import MessageQueue, IPC_CREX, BusyError
from threading import Thread, Lock, Event
from threading import Semaphore as pySem
from concurrent.futures import ThreadPoolExecutor

from pocket_tf_if import PocketControl, TFFunctions, ReturnValue, TFDataType, CLIENT_TO_SERVER, SERVER_TO_CLIENT, SharedMemoryChannel
os.chdir('/root/yolov3-tf2')
LIBC = CDLL(find_library('c'))

GLOBAL_SLEEP = 0.01
LOCAL_SLEEP = 0.0001
POCKETD_SOCKET_PATH = '/tmp/pocketd.sock'
DEVICE_LIST_AVAILABLE = False
DEVICE_LIST = []
ADD_INTERVAL = 0.01
DEDUCT_INTERVAL = 0.01

def debug(*args):
    import inspect
    filename = inspect.stack()[1].filename
    lineno = inspect.stack()[1].lineno
    caller = inspect.stack()[1].function
    print(f'debug>> [{filename}:{lineno}, {caller}]', *args)

MEM_SEM = pySem()
CPU_SEM = pySem()
class Utils:

    @staticmethod
    def get_container_id():
        cg = open('/proc/self/cgroup')
        content = cg.readlines()
        for line in content:
            if 'docker' in line:
                cid = line.strip().split('/')[-1]
                return cid
    
    @staticmethod
    def round_up_to_even(f):
        return int(math.ceil(f / 2.) * 2)

    @staticmethod
    def get_memory_limit(client_id = None):
        if client_id != None:
            with open(f'/cg/memory/docker/{client_id}/memory.limit_in_bytes', 'r') as limit_in_bytes:
                memory_limit = int(limit_in_bytes.read().strip())
            return memory_limit
        else:
            with open('/sys/fs/cgroup/memory/memory.limit_in_bytes', 'r') as limit_in_bytes:
                memory_limit = int(limit_in_bytes.read().strip())
            return memory_limit

    @staticmethod
    def get_memory_usage(client_id = None):
        if client_id != None:
            with open(f'/cg/memory/docker/{client_id}/memory.usage_in_bytes', 'r') as usage_in_bytes:
                memory_usage = int(usage_in_bytes.read().strip())
        else:
            with open('/sys/fs/cgroup/memory/memory.usage_in_bytes', 'r') as usage_in_bytes:
                memory_usage = int(usage_in_bytes.read().strip())
        return memory_usage

    @staticmethod
    def get_cpu_limit(client_id = None):
        if client_id != None:
            with open(f'/cg/cpu/docker/{client_id}/cpu.cfs_period_us', 'r') as cfs_period_us:
                cfs_period_us = int(cfs_period_us.read().strip())
            with open(f'/cg/cpu/docker/{client_id}/cpu.cfs_quota_us', 'r') as cfs_quota_us:
                cfs_quota_us = int(cfs_quota_us.read().strip())
            return cfs_quota_us, cfs_period_us
        else:
            with open(f'/sys/fs/cgroup/cpu/cpu.cfs_period_us', 'r') as cfs_period_us:
                cfs_period_us = int(cfs_period_us.read().strip())
            with open(f'/sys/fs/cgroup/cpu/cpu.cfs_quota_us', 'r') as cfs_quota_us:
                cfs_quota_us = int(cfs_quota_us.read().strip())
            return cfs_quota_us, cfs_period_us

    ### remove
    @staticmethod
    def request_memory_move():
        with open('/sys/fs/cgroup/memory/memory.limit_in_bytes', 'r') as limit_in_bytes:
            memory_limit = float(limit_in_bytes.read().strip()) * RSRC_REALLOC_RATIO
        return memory_limit

    ### remove 
    @staticmethod
    def request_cpu_move():
        with open(f'/sys/fs/cgroup/cpu/cpu.cfs_period_us', 'r') as cfs_period_us:
            cpu_denominator = float(cfs_period_us.read().strip())
        with open(f'/sys/fs/cgroup/cpu/cpu.cfs_quota_us', 'r') as cfs_quota_us:
            cpu_numerator = float(cfs_quota_us.read().strip())
        return (cpu_numerator/cpu_denominator) * RSRC_REALLOC_RATIO, cpu_numerator, cpu_denominator

    @staticmethod
    def deduct_resource(client_id, mem, cfs_quota_us, cfs_period_us):
        global DEDUCT_INTERVAL
        if cfs_period_us != 100000:
            raise Exception("cfs_period_us should be 100000")
        
        CPU_SEM.acquire()
        MEM_SEM.acquire()

        fe_mem_int = Utils.get_memory_limit(client_id) + mem
        fe_cfs_quota, fe_cfs_period = Utils.get_cpu_limit(client_id)
        fe_cpu_int = fe_cfs_quota + cfs_quota_us

        be_mem_int = Utils.get_memory_limit() - mem
        be_cfs_quota, be_cfs_period = Utils.get_cpu_limit()
        be_cpu_int = be_cfs_quota - cfs_quota_us

        # debug(f'old-->cpu={Utils.get_cpu_limit()}) - {cfs_quota_us}, mem={Utils.get_memory_limit()} - {mem}')

        if mem != 0:
            try:
                # Checks if memory limit to be < current usage.
                # current_usage = Utils.get_memory_usage()
                # if current_usage >= be_mem_int:
                #     difference = current_usage - be_mem_int
                #     page_size = LIBC.getpagesize()
                #     how_many_pages = ceil(difference/page_size)
                #     num_bytes_to_evict = page_size * how_many_pages
                #     tmp_ptr = c_void_p()
                #     ret = LIBC.posix_memalign(byref(tmp_ptr), page_size, num_bytes_to_evict)
                #     if ret != 0:
                #         raise Exception('ENOMEM')
                #     c_char_ptr = cast(tmp_ptr, POINTER(c_char * num_bytes_to_evict))
                #     for i in range(0, how_many_pages):
                #         c_char_ptr.contents[i*page_size] = c_char(0xff)
                #     LIBC.free(tmp_ptr)
                    
                with open('/sys/fs/cgroup/memory/memory.limit_in_bytes', 'w') as be_limit:
                    be_limit.write(str(be_mem_int).strip())
                # with open('/sys/fs/cgroup/memory/memory.memsw.limit_in_bytes', 'w') as be_swap_limit:
                #     be_swap_limit.write(str(be_mem_int*4).strip())

                # with open(f'/cg/memory/docker/{client_id}/memory.memsw.limit_in_bytes', 'w') as fe_swap_limit:
                #     fe_swap_limit.write(str(fe_mem_int*4).strip())
                with open(f'/cg/memory/docker/{client_id}/memory.limit_in_bytes', 'w') as fe_limit:
                    fe_limit.write(str(fe_mem_int).strip())

            except Exception as e:
                mem_fail = True
                debug(repr(e), e)

        if cfs_quota_us != 0:
            try:
                with open(f'/cg/cpu/docker/{client_id}/cpu.cfs_quota_us', 'w') as cfs_quota_us:
                    cfs_quota_us.write(str(fe_cpu_int).strip())
                with open('/sys/fs/cgroup/cpu/cpu.cfs_quota_us', 'w') as cfs_quota_us:
                    cfs_quota_us.write(str(be_cpu_int).strip())
            except Exception as e:
                cpu_fail = True
                debug(repr(e), e)
                debug(f'client_id={client_id}, fe_cpu_int={fe_cpu_int}, be_cpu_int={be_cpu_int}')

        MEM_SEM.release()
        CPU_SEM.release()


    @staticmethod
    def add_resource(client_id, mem, cfs_quota_us, cfs_period_us):
        global ADD_INTERVAL
        if cfs_period_us != 100000:
            raise Exception("cfs_period_us should be 100000")

        CPU_SEM.acquire()
        MEM_SEM.acquire()
            
        fe_mem_int = Utils.get_memory_limit(client_id) - mem
        fe_cfs_quota, fe_cfs_period = Utils.get_cpu_limit(client_id)
        fe_cpu_int = fe_cfs_quota - cfs_quota_us

        be_mem_int = Utils.get_memory_limit() + mem
        be_cfs_quota, be_cfs_period = Utils.get_cpu_limit()
        be_cpu_int = be_cfs_quota + cfs_quota_us

        debug(f'old-->cpu={Utils.get_cpu_limit()}) + {cfs_quota_us}, mem={Utils.get_memory_limit()} + {mem}')

        if mem != 0:
            try:
                # Checks if memory limit to be < current usage.
                current_usage = Utils.get_memory_usage(client_id)
                if current_usage >= fe_mem_int:
                    pid = PocketManager.get_instance().fe_to_pid.get(client_id)
                    debug(f'pid={pid}')
                    import resource
                    resource.prlimit(pid, resource.RLIMIT_RSS, (fe_mem_int, fe_mem_int))
                    # difference = current_usage - fe_mem_int
                    # page_size = LIBC.getpagesize()
                    # how_many_pages = ceil(difference/page_size)
                    # num_bytes_to_evict = page_size * how_many_pages *2
                    # tmp_ptr = c_void_p()
                    # ret = LIBC.posix_memalign(byref(tmp_ptr), page_size, num_bytes_to_evict)
                    # if ret != 0:
                    #     raise Exception('ENOMEM')
                    # c_char_ptr = cast(tmp_ptr, POINTER(c_char * num_bytes_to_evict))
                    # for i in range(0, how_many_pages):
                    #     c_char_ptr.contents[i*page_size] = c_char(0xff)
                    # # madvise = LIBC.madvise
                    # # madvise.argtypes = [c_void_p, c_size_t, c_int]
                    # # madvise.restype = c_int
                    # # debug(tmp_ptr, tmp_ptr.value, num_bytes_to_evict)
                    # LIBC.free(tmp_ptr)
                    # #define MADV_FREE       8               /* free pages only if memory pressure */
                    # #define MADV_DONTNEED	4		/* don't need these pages */
                    # #define MADV_REMOVE	9		/* remove these pages & resources */
                    # #define MADV_SOFT_OFFLINE 101		/* soft offline page for testing */

                    # ret = madvise(tmp_ptr, num_bytes_to_evict, 8)
                    # if  ret != 0:
                    #     debug(f'return={ret}')

                # with open(f'/cg/memory/docker/{client_id}/memory.memsw.limit_in_bytes', 'w') as fe_swap_limit:
                #     try:
                #         fe_swap_limit.write(str(10*1024*1024*1024).strip())
                #     except:
                #         raise Exception('OutOfMemory')
                with open(f'/cg/memory/docker/{client_id}/memory.limit_in_bytes', 'w') as fe_limit:
                    fe_limit.write(str(fe_mem_int).strip())
                # with open(f'/cg/memory/docker/{client_id}/memory.memsw.limit_in_bytes', 'w') as fe_swap_limit:
                #     try:
                #         fe_swap_limit.write(str(fe_mem_int*4).strip())
                #     except:
                #         raise Exception('OutOfMemory')

                # with open('/sys/fs/cgroup/memory/memory.memsw.limit_in_bytes', 'w') as be_swap_limit:
                #     be_swap_limit.write(str(be_mem_int*4).strip())
                with open('/sys/fs/cgroup/memory/memory.limit_in_bytes', 'w') as be_limit:
                    be_limit.write(str(be_mem_int).strip())
            except Exception as e:
                mem_fail = True
                debug(repr(e), e)

        if cfs_quota_us != 0:
            try:
                with open(f'/cg/cpu/docker/{client_id}/cpu.cfs_quota_us', 'w') as cfs_quota_us:
                    cfs_quota_us.write(str(fe_cpu_int).strip())
                with open('/sys/fs/cgroup/cpu/cpu.cfs_quota_us', 'w') as cfs_quota_us:
                    cfs_quota_us.write(str(be_cpu_int).strip())
            except Exception as e:
                cpu_fail = True
                debug(repr(e), e)

        MEM_SEM.release()
        CPU_SEM.release()

    @staticmethod
    def deduct_resource_daemon(client_id, mem, cfs_quota_us, cfs_period_us):
        global DEDUCT_INTERVAL
        import socket
        if cfs_period_us != 100000:
            raise Exception("cfs_period_us should be 100000")
        
        CPU_SEM.acquire()
        MEM_SEM.acquire()

        # fe_mem_int = Utils.get_memory_limit(client_id) + mem
        # fe_cfs_quota, fe_cfs_period = Utils.get_cpu_limit(client_id)
        # fe_cpu_int = fe_cfs_quota + cfs_quota_us

        # be_mem_int = Utils.get_memory_limit() - mem
        # be_cfs_quota, be_cfs_period = Utils.get_cpu_limit()
        # be_cpu_int = be_cfs_quota - cfs_quota_us

        # debug(f'old-->cpu={Utils.get_cpu_limit()}) - {cfs_quota_us}, mem={Utils.get_memory_limit()} - {mem}')


        if mem != 0 or cfs_quota_us != 0:
            my_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            my_socket.connect(POCKETD_SOCKET_PATH)
            args_dict = {'sender'   : 'FE',
                        'command'  : 'migrate_resource',
                        'client'   : Utils.get_container_id(), 
                        'be'       : client_id,
                        'mem'      : mem,
                        'cpu'      : cfs_quota_us,
                        'cpudenom' : cfs_period_us}
            json_data_to_send = json.dumps(args_dict)
            my_socket.send(json_data_to_send.encode('utf-8'))
            data_received = my_socket.recv(1024)
            my_socket.close()

        MEM_SEM.release()
        CPU_SEM.release()


    @staticmethod
    def add_resource_daemon(client_id, mem, cfs_quota_us, cfs_period_us):
        global ADD_INTERVAL
        import socket
        if cfs_period_us != 100000:
            raise Exception("cfs_period_us should be 100000")

        CPU_SEM.acquire()
        MEM_SEM.acquire()
            
        # fe_mem_int = Utils.get_memory_limit(client_id) - mem
        # fe_cfs_quota, fe_cfs_period = Utils.get_cpu_limit(client_id)
        # fe_cpu_int = fe_cfs_quota - cfs_quota_us

        # be_mem_int = Utils.get_memory_limit() + mem
        # be_cfs_quota, be_cfs_period = Utils.get_cpu_limit()
        # be_cpu_int = be_cfs_quota + cfs_quota_us

        # debug(f'old-->cpu={Utils.get_cpu_limit()}) + {cfs_quota_us}, mem={Utils.get_memory_limit()} + {mem}')

        if mem != 0 or cfs_quota_us != 0:
            my_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            my_socket.connect(POCKETD_SOCKET_PATH)
            args_dict = {'sender'   : 'FE',
                        'command'  : 'migrate_resource',
                        'client'   : client_id, 
                        'be'       : Utils.get_container_id(),
                        'mem'      : mem,
                        'cpu'      : cfs_quota_us,
                        'cpudenom' : cfs_period_us}
            json_data_to_send = json.dumps(args_dict)
            my_socket.send(json_data_to_send.encode('utf-8'))
            data_received = my_socket.recv(1024)
            my_socket.close()

        MEM_SEM.release()
        CPU_SEM.release()

### moved from apps
class BatchNormalization(tf.keras.layers.BatchNormalization):
    """
    Make trainable=False freeze BN for real (the og version is sad)
    """

    def call(self, x, training=False):
        if training is None:
            training = tf.constant(False)
        training = tf.logical_and(training, self.trainable)
        return super().call(x, training)

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

yolo_anchors = np.array([(10, 13), (16, 30), (33, 23), (30, 61), (62, 45),
                         (59, 119), (116, 90), (156, 198), (373, 326)],
                        np.float32) / 416
yolo_anchor_masks = np.array([[6, 7, 8], [3, 4, 5], [0, 1, 2]])

# but don't delete
flags.DEFINE_integer('yolo_max_boxes', 100,
                     'maximum number of boxes per image')
flags.DEFINE_float('yolo_iou_threshold', 0.5, 'iou threshold')
flags.DEFINE_float('yolo_score_threshold', 0.5, 'score threshold')


def stack_trace():
    import traceback
    traceback.print_tb()
    traceback.print_exception()
    traceback.print_stack()

# def str_replacer(old, new, start):
#     if start not in range(len(old)):
#         raise ValueError("invalid start index")

#     # if start < 0:
#     #     return new + old
#     # if start > len(old):
#     #     return old + new

#     return old[:start] + new + old[start + 1:]

### test_code
# from multiprocessing import Process, Manager ## test_code
# manager = Manager() ## test_code
# _matmultest_dict = manager.dict() ## test_code
_matmultest_dict = {} ## test_code
from math import sqrt
# class ThreadWithReturnValue(Thread):
#     def __init__(self, group=None, target=None, name=None,
#                  args=(), kwargs=None, *, daemon=None):
#         # Call the Thread class's init function
#         Thread.__init__(self)
#         self._return = None

#     def run(self):
#         if self._Thread__target is not None:
#             self._return = self._Thread__target(*self._Thread__args,
#                                                 **self._Thread__kwargs)
#     def join(self):
#         Thread.join(self)
#         return self._return

class TensorFlowServer:
    @staticmethod
    def hello(client_id, message):
        return_dict = {'message': message}
        return ReturnValue.OK.value, return_dict

    @staticmethod
    def _noptest(client_id):
        try:
            # do nothing
            pass
        except Exception as e:
            import inspect
            from inspect import currentframe, getframeinfo
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': inspect.stack()[0][3]}
        else:
            return ReturnValue.OK.value, None
        finally:
            pass

    @staticmethod
    def _matmultest(client_id, N): ## test_code
        try:
            mat_a = np.random.randint(0, sqrt(sys.maxsize), size=(N, N))
            mat_b = np.random.randint(0, sqrt(sys.maxsize), size=(N, N))
            # for r in range(N):
            #     for c in range(N):
            #         for k in range(N):
            #             mat_c[r, c] = mat_a[r, k] * mat_b[k, c]
            # mat_c = np.matmul(mat_a, mat_b)            
            if client_id not in _matmultest_dict:
                _matmultest_dict[client_id] = []
            _matmultest_dict[client_id].append(mat_a)
            _matmultest_dict[client_id].append(mat_b)

            # import ctypes
            # filepath = '/root/tfrpc/server/test/libmatmul.so'
            # if not os.path.exists(filepath):
            #     print(os.getcwd())
            #     print(subprocess.check_output('ls -alh /root/tfrpc/server/test/', shell=True, encoding='utf8'))
            #     raise Exception('Library file does not exist, consider build it first.')

            # matmullib = ctypes.CDLL(filepath)
            # matmullib.matmul.argtypes = [ctypes.c_int]
            # matmullib.matmul.restype = ctypes.c_void_p
            # result_mat = matmullib.matmul(N)
            # # t = ThreadWithReturnValue(target=matmullib.matmul, args=(N,))
            # # t = Thread(target=matmullib.matmul, args=(N,))
            # # t.start()
            # # # result_mat = t.join()
            # # t.join()
            # if client_id not in _matmultest_dict:
            #     _matmultest_dict[client_id] = []
            # _matmultest_dict[client_id].append(result_mat)
        except Exception as e:
            import inspect
            from inspect import currentframe, getframeinfo
            print(e)
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': inspect.stack()[0][3]}
        else:
            return ReturnValue.OK.value, None
        finally:
            pass

    @staticmethod
    def check_if_model_exist(client_id, model_name):
        keras_model = None
        if model_name in PocketManager.get_instance().model_dict:
            exist_value = True
            model = PocketManager.get_instance().model_dict[model_name]
            keras_model = TFDataType.Model(model_name, id(model), already_built=True).to_dict()
            PocketManager.get_instance().add_object_to_per_client_store(client_id, model)
        else:
            PocketManager.get_instance().dict_modelname_to_session[model_name] = tf.Graph()
            # PocketManager.get_instance().dict_modelname_to_session[model_name] = tf.compat.v1.Session(graph=tf.Graph())
            PocketManager.get_instance().dict_clientid_to_modelname[client_id] = model_name
            exist_value = False

        return ReturnValue.OK.value, (exist_value, keras_model)

    @staticmethod
    def tf_callable(client_id, typename, callable, args, _shmem=None):
        try:
            callable_instance = PocketManager.get_instance().get_real_object_with_mock(client_id, callable)
            real_args = []
            PocketManager.get_instance().disassemble_args(client_id, args, real_args)
            # debug(real_args)
            ret = callable_instance(*real_args)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            debug(tb)
            from inspect import currentframe, getframeinfo, stack
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': stack()[0][3]}
        else:
            if type(ret) in (list, tuple):
                ret_list = []
                for index, elem in enumerate(ret):
                    PocketManager.get_instance().add_object_to_per_client_store(client_id, elem)
                    try:
                        ret_list.append(TFDataType.Tensor(elem.name, id(elem), elem.shape.as_list()).to_dict())
                    except AttributeError as e:
                        ret_list.append(TFDataType.Tensor(None, id(elem), elem.shape.as_list()).to_dict())
                        
                return ReturnValue.OK.value, ret_list
            elif type(ret) is dict:
                ret_dict = {} # optim 2 # todo: pseudo dict implementation needed. for object det
                # s = time()
                # for key, value in ret.items():
                #     ret[key] = value.numpy().tolist()
                # t1 = time()
                # json_dumps = json.dumps(ret)
                # t11 = time()
                # json_converted = bytes(json_dumps, encoding='utf8')
                # t2 = time()
                # length = len(json_converted)
                # t3 = time()
                # # PocketManager.get_instance().shmem_dict[client_id].write(contents=json_converted) # optim 1
                # ret_dict={'shmem': {'length':length}}
                # e = time()
                # print(f'\ttime={e-s}, {t1-s}, {t11-t1},{t2-t11}, {t3-t2}, {e-t3}')

                return ReturnValue.OK.value, ret_dict

            else:
                PocketManager.get_instance().add_object_to_per_client_store(client_id, ret)
                try:
                    name = ret.name
                except AttributeError as e:
                    name=None
                try:
                    shape = ret.shape.as_list()
                except AttributeError as e:
                    shape = None
                return ReturnValue.OK.value, TFDataType.Tensor(name, id(ret), shape).to_dict()
        finally:
            pass

    @staticmethod
    def object_slicer(client_id, mock_dict, key):
        try:
            object = PocketManager.get_instance().get_real_object_with_mock(client_id, mock_dict)
            # debug(f'object={object}')
            tensor = object[key]
        except Exception as e:
            import inspect
            from inspect import currentframe, getframeinfo
            # debug(key)
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': inspect.stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, tensor)
            try:
                mock_tensor = TFDataType.Tensor(tensor.name, id(tensor), tensor.shape.as_list(), tensor)
                ret = mock_tensor.to_dict()
            except AttributeError as e:
                mock_tensor = TFDataType.Tensor(None, id(tensor), tensor.shape.as_list(), tensor)
                ret = mock_tensor.to_dict()
            finally:
                return ReturnValue.OK.value, ret
        finally:
            pass

    @staticmethod
    def tensor_division(client_id, mock_dict, other):
        try:
            # debug(f'mock_dict={mock_dict} other={other}')
            object = PocketManager.get_instance().get_real_object_with_mock(client_id, mock_dict)
            tensor = object / other
        except Exception as e:
            import inspect
            from inspect import currentframe, getframeinfo
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': inspect.stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, tensor)
            return ReturnValue.OK.value, TFDataType.Tensor(None, id(tensor), tensor.shape.as_list()).to_dict()
        finally:
            pass

    # @staticmethod
    # def tensor_shape(client_id, mock_dict):
    #     try:
    #         # debug(f'mock_dict={mock_dict} other={other}')
    #         object = PocketManager.get_instance().get_real_object_with_mock(client_id, mock_dict)
    #         shape = object.shape.as_list()
    #     except Exception as e:
    #         import inspect
    #         from inspect import currentframe, getframeinfo
    #         frameinfo = getframeinfo(currentframe())
    #         return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': inspect.stack()[0][3]}
    #     else:
    #         return ReturnValue.OK.value, shape
    #     finally:
    #         pass

    # @staticmethod
    # def __substitute_closure_vars_with_context(function, context):
    #     new_string = function
    #     debug(context)
    #     for key, value in context.copy().items():
    #         index = 0
    #         while index < len(function):
    #             if function[index:].startswith(key) and \
    #                not function[index-1].isalnum() and \
    #                not function[index+len(key)].isalnum():
    #                substitute = str(value)
    #                new_string = function[:index] + function[index:].replace(key, substitute, 1)
    #                function = new_string
    #             index += 1
    #         function = new_string
    #     return function


    @staticmethod
    def tensor_division(client_id, mock_dict, other):
        try:
            # debug(f'mock_dict={mock_dict} other={other}')
            object = PocketManager.get_instance().get_real_object_with_mock(client_id, mock_dict)
            tensor = object / other
        except Exception as e:
            import inspect
            from inspect import currentframe, getframeinfo
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': inspect.stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, tensor)
            return ReturnValue.OK.value, TFDataType.Tensor(None, id(tensor), tensor.shape.as_list()).to_dict()
        finally:
            pass

    # @staticmethod
    # def __substitute_closure_vars_with_context(function, context):
    #     new_string = function
    #     debug(context)
    #     for key, value in context.copy().items():
    #         index = 0
    #         while index < len(function):
    #             if function[index:].startswith(key) and \
    #                not function[index-1].isalnum() and \
    #                not function[index+len(key)].isalnum():
    #                substitute = str(value)
    #                new_string = function[:index] + function[index:].replace(key, substitute, 1)
    #                function = new_string
    #             index += 1
    #         function = new_string
    #     return function


    @staticmethod
    def tf_shape(client_id, input, out_type, name=None):
        try:
            out_type = eval(out_type)
            input = PocketManager.get_instance().get_real_object_with_mock(client_id, input)
            tensor = tf.shape(input=input, out_type=out_type, name=name)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            debug(tb)
            from inspect import currentframe, getframeinfo, stack
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, tensor)
            return ReturnValue.OK.value, TFDataType.Tensor(tensor.name,
                                                           id(tensor),
                                                           tensor.shape.as_list()).to_dict()
        finally:
            pass

    @staticmethod
    def tf_reshape(client_id, tensor, shape, name=None):
        try:
            tensor = PocketManager.get_instance().get_real_object_with_mock(client_id, tensor)
            # debug(tensor)
            # debug(shape)
            returned_tensor = tf.reshape(tensor=tensor, shape=shape, name=name)
            # debug(returned_tensor)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            # debug(tb)
            from inspect import currentframe, getframeinfo, stack
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, returned_tensor)
            try:
                name = returned_tensor.name
            except AttributeError as e:
                name=None
            try:
                shape = returned_tensor.shape.as_list()
            except AttributeError as e:
                shape = None
            return ReturnValue.OK.value, TFDataType.Tensor(name, 
                                                           id(returned_tensor), 
                                                           shape).to_dict()
        finally:
            pass

    @staticmethod
    def tf_constant(client_id, value, dtype=None, shape=None, name='Const'):
        try:
            length = value
            value = str(PocketManager.get_instance().shmem_dict[client_id].read(length), 'utf-8').split(';')
            tensor = tf.constant(value=value, dtype=dtype, shape=shape, name=name)
            # debug(returned_tensor)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            # debug(tb)
            from inspect import currentframe, getframeinfo, stack
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, tensor)
            try:
                name = tensor.name
            except AttributeError as e:
                name=None
            try:
                shape = tensor.shape.as_list()
            except AttributeError as e:
                shape = None
            return ReturnValue.OK.value, TFDataType.Tensor(name,
                                                           id(tensor),
                                                           shape).to_dict()
        finally:
            pass


    @staticmethod
    def tf_sigmoid(client_id, x, name=None):
        try:
            if type(x) == dict and 'obj_id' in x:
                x = PocketManager.get_instance().get_real_object_with_mock(client_id, x)

            tensor = tf.sigmoid(x=x, name=name)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            # debug(tb)
            from inspect import currentframe, getframeinfo, stack
            frameinfo = getframeinfo(currentframe())
            print(e)
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': stack()[0][3]}
        else:
            return ReturnValue.OK.value, tensor.numpy().tolist()
        finally:
            pass


    @staticmethod
    def tf_config_experimental_list__physical__devices(client_id, device_type):
        global DEVICE_LIST, DEVICE_LIST_AVAILABLE
        if DEVICE_LIST_AVAILABLE:
            return_list = DEVICE_LIST
        else:
            device_list = tf.config.experimental.list_physical_devices(device_type)
            return_list = []
            DEVICE_LIST_AVAILABLE = True
            for elem in device_list:
                return_list.append(TFDataType.PhysicalDevice(dict=elem.__dict__))
            DEVICE_LIST = return_list
            # return_list.append(TFDataType.PhysicalDevice(elem.name, elem.device_type).to_dict())
        return ReturnValue.OK.value, return_list

    @staticmethod
    def tf_config_experimental_set__memory__growth(client_id, device, enable):
        try:
            tf.config.experimental.set_memory_growth(device, enable)
        except Exception as e:
            import inspect
            from inspect import currentframe, getframeinfo
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': inspect.stack()[0][3]}
        else:
            return ReturnValue.OK.value, []
        finally:
            pass

    @staticmethod
    def tf_keras_layers_Input(client_id, shape=None, batch_size=None, name=None, dtype=None, sparse=False, tensor=None, ragged=False, **kwargs):
        try:
            tensor = tf.keras.layers.Input(shape=shape, batch_size=batch_size, name=name, dtype=dtype, sparse=sparse, tensor=tensor, ragged=ragged, **kwargs)
        except Exception as e:
            import inspect
            from inspect import currentframe, getframeinfo
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': inspect.stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, tensor)
            return ReturnValue.OK.value, TFDataType.Tensor(tensor.name, 
                                                           id(tensor), 
                                                           tensor.shape.as_list()).to_dict()
        finally:
            pass

    @staticmethod
    def tf_keras_layers_Conv2D(client_id, filters, kernel_size, strides=(1, 1),
        padding='valid', data_format=None,
        dilation_rate=(1, 1), activation=None, use_bias=True,
        kernel_initializer='glorot_uniform', bias_initializer='zeros',
        kernel_regularizer=None, bias_regularizer=None, activity_regularizer=None,
        kernel_constraint=None, bias_constraint=None, **kwargs):
        # debug('\ntf_keras_layers_Conv2D')

        kernel_regularizer = PocketManager.get_instance().get_real_object_with_mock(client_id, kernel_regularizer)

        try:

            tensor = tf.keras.layers.Conv2D(filters=filters, kernel_size=kernel_size, strides=strides, padding=padding, data_format=data_format, dilation_rate=dilation_rate, activation=activation, use_bias=use_bias, kernel_initializer=kernel_initializer, bias_initializer=bias_initializer, kernel_regularizer=kernel_regularizer, bias_regularizer=bias_regularizer, activity_regularizer=activity_regularizer, kernel_constraint=kernel_constraint, bias_constraint=bias_constraint, **kwargs)
            # debug(f'tensor_name={tensor.name}')
        except Exception as e:
            import inspect
            from inspect import currentframe, getframeinfo
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': inspect.stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, tensor)
            return ReturnValue.OK.value, TFDataType.Conv2D(tensor.name, 
                                                           id(tensor)).to_dict()
        finally:
            pass

    @staticmethod
    def tf_keras_layers_ZeroPadding2D(client_id, padding=(1, 1), data_format=None, **kwargs):
        try:
            tensor = tf.keras.layers.ZeroPadding2D(padding=padding, data_format=data_format, **kwargs)
        except Exception as e:
            import inspect
            from inspect import currentframe, getframeinfo
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': inspect.stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, tensor)
            return ReturnValue.OK.value, TFDataType.ZeroPadding2D(tensor.name, 
                                                                  id(tensor)).to_dict()
        finally:
            pass

    @staticmethod
    def tf_keras_regularizers_l2(client_id, l=0.01):
        try:
            l2 = tf.keras.regularizers.l2(l=l)
        except Exception as e:
            import inspect
            from inspect import currentframe, getframeinfo
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': inspect.stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, l2)
            # return ReturnValue.OK.value, TFDataType.L2(id(l2)).to_dict()
            return ReturnValue.OK.value, TFDataType.L2(id(l2)).to_dict()
        finally:
            pass

    @staticmethod
    def tf_keras_layers_BatchNormalization(client_id, axis=-1, momentum=0.99, epsilon=0.001, center=True, scale=True,
    beta_initializer='zeros', gamma_initializer='ones',
    moving_mean_initializer='zeros', moving_variance_initializer='ones',
    beta_regularizer=None, gamma_regularizer=None, beta_constraint=None,
    gamma_constraint=None, renorm=False, renorm_clipping=None, renorm_momentum=0.99,
    fused=None, trainable=True, virtual_batch_size=None, adjustment=None, name=None,
    **kwargs):
        try:
            tensor = BatchNormalization(axis=axis, momentum=momentum, epsilon=epsilon, center=center, scale=scale,
            beta_initializer=beta_initializer, gamma_initializer=gamma_initializer,
            moving_mean_initializer=moving_mean_initializer, moving_variance_initializer=moving_variance_initializer,
            beta_regularizer=beta_regularizer, gamma_regularizer=gamma_regularizer, beta_constraint=beta_constraint,
            gamma_constraint=gamma_constraint, renorm=renorm, renorm_clipping=renorm_clipping, renorm_momentum=renorm_momentum,
            fused=fused, trainable=trainable, virtual_batch_size=virtual_batch_size, adjustment=adjustment, name=name,
            **kwargs)
        except Exception as e:
            import inspect
            from inspect import currentframe, getframeinfo
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': inspect.stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, tensor)
            return ReturnValue.OK.value, TFDataType.BatchNormalization(tensor.name, 
                                                                       id(tensor)).to_dict()
        finally:
            pass

    @staticmethod
    def tf_keras_layers_LeakyReLU(client_id, alpha=0.3, **kwargs):
        try:
            tensor = tf.keras.layers.LeakyReLU(alpha=alpha, **kwargs)
        except Exception as e:
            import inspect
            from inspect import currentframe, getframeinfo
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': inspect.stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, tensor)
            return ReturnValue.OK.value, TFDataType.LeakyReLU(tensor.name, id(tensor)).to_dict()
        finally:
            pass

    @staticmethod
    def tf_keras_layers_Add(client_id, **kwargs):
        try:
            tensor = tf.keras.layers.Add(**kwargs) ###
        except Exception as e:
            import inspect
            from inspect import currentframe, getframeinfo
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': inspect.stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, tensor)
            return ReturnValue.OK.value, TFDataType.Add(tensor.name, id(tensor)).to_dict()
        finally:
            pass

    @staticmethod
    def tf_keras_Model(client_id, args, **kwargs):
        try:
            real_args = []
            PocketManager.get_instance().disassemble_args(client_id, args, real_args)

            real_kwargs = {}
            PocketManager.get_instance().disassemble_kwargs(client_id, kwargs, real_kwargs)
            model = tf.keras.Model(*real_args, **real_kwargs) ###
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            debug(tb)
            from inspect import currentframe, getframeinfo, stack
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, model)
            PocketManager.get_instance().add_built_model(name=model.name, model=model)
            return ReturnValue.OK.value, TFDataType.Model(name=model.name,
                                                          obj_id=id(model)).to_dict()
        finally:
            pass

    @staticmethod
    def tf_keras_layers_Lambda(client_id, function, output_shape=None, mask=None, arguments=None, **kwargs):
        try:
            function = eval(function)
            tensor = tf.keras.layers.Lambda(function=function, output_shape=output_shape, mask=mask, arguments=arguments, **kwargs)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            debug(tb)
            from inspect import currentframe, getframeinfo, stack
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, tensor)
            return ReturnValue.OK.value, TFDataType.Model(name=tensor.name,
                                                          obj_id=id(tensor)).to_dict()
        finally:
            pass

    @staticmethod
    def tf_keras_layers_UpSampling2D(client_id, size=(2, 2), data_format=None, interpolation='nearest', **kwargs):
        try:
            tensor = tf.keras.layers.UpSampling2D(size=size, data_format=data_format, interpolation=interpolation, **kwargs)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            debug(tb)
            from inspect import currentframe, getframeinfo, stack
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, tensor)
            return ReturnValue.OK.value, TFDataType.Model(name=tensor.name,
                                                          obj_id=id(tensor)).to_dict()
        finally:
            pass

    @staticmethod
    def tf_keras_layers_Concatenate(client_id, axis=-1, **kwargs):
        try:
            tensor = tf.keras.layers.Concatenate(axis=axis, **kwargs)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            debug(tb)
            from inspect import currentframe, getframeinfo, stack
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, tensor)
            return ReturnValue.OK.value, TFDataType.Model(name=tensor.name,
                                                          obj_id=id(tensor)).to_dict()
        finally:
            pass

    # @tf.function
    @staticmethod
    def tf_image_decode__image(client_id, contents, channels=None, dtype='tf.dtypes.uint8', name=None, expand_animations=True):
        try:
            dtype = eval(dtype)
            contents = bytes(PocketManager.get_instance().shmem_dict[client_id].read(contents))
            format = what(None, h=contents)
            if format == 'png':
                tensor = tf.image.decode_png(contents=contents, channels=channels, dtype=dtype, name=name)
            elif format == 'jpeg':
                tensor = tf.image.decode_png(contents=contents, channels=channels, dtype=dtype, name=name)
            else:
                tensor = tf.image.decode_image(contents=contents, channels=channels, dtype=dtype, name=name, expand_animations=expand_animations)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            debug(tb)
            from inspect import currentframe, getframeinfo, stack
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, tensor)
            return ReturnValue.OK.value, TFDataType.Tensor(name=None,
                                                          obj_id=id(tensor), 
                                                          shape=tensor.shape.as_list()).to_dict()
        finally:
            pass

    @staticmethod
    def model_load_weights(client_id, model, filepath, by_name=False, skip_mismatch=False):
        try:
            # debug(client_id, model)
            model = PocketManager.get_instance().get_real_object_with_mock(client_id, model)
            model.load_weights(filepath=filepath, by_name=by_name, skip_mismatch=skip_mismatch)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            debug(tb)
            from inspect import currentframe, getframeinfo, stack
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': stack()[0][3]}
        else:
            # PocketManager.get_instance().add_object_to_per_client_store(client_id, tensor)
            return ReturnValue.OK.value, None
        finally:
            pass

    @staticmethod
    def tf_expand__dims(client_id, input, axis, name=None):
        try:
            input = PocketManager.get_instance().get_real_object_with_mock(client_id, input)
            tensor = tf.expand_dims(input=input, axis=axis, name=name)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            debug(tb)
            from inspect import currentframe, getframeinfo, stack
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, tensor)
            return ReturnValue.OK.value, TFDataType.Tensor(name=None,
                                                          obj_id=id(tensor)).to_dict()
        finally:
            pass

    @staticmethod
    def tf_image_resize(client_id, images, size, method=tf.image.ResizeMethod.BILINEAR, preserve_aspect_ratio=False,
    antialias=False, name=None):
        try:
            images = PocketManager.get_instance().get_real_object_with_mock(client_id, images)
            tensor = tf.image.resize(images=images, size=size, method=method, preserve_aspect_ratio=preserve_aspect_ratio, antialias=antialias, name=name)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            debug(tb)
            from inspect import currentframe, getframeinfo, stack
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, tensor)
            return ReturnValue.OK.value, TFDataType.Tensor(name=None,
                                                          obj_id=id(tensor),
                                                          shape=tensor.shape.as_list()).to_dict()
        finally:
            pass

    @staticmethod
    def tf_keras_applications_MobileNetV2(client_id, args, **kwargs):
        try:
            if 'mobilenetv2' in PocketManager.get_instance().model_dict:
                model = PocketManager.get_instance().model_dict['mobilenetv2']
                PocketManager.get_instance().add_object_to_per_client_store(client_id, model)
                return ReturnValue.OK.value, TFDataType.Model(name='mobilenetv2',
                                                            obj_id=id(model),
                                                            already_built=True).to_dict()
            PocketManager.get_instance().dict_clientid_to_modelname[client_id]='mobilenetv2'
            
            real_args = []
            PocketManager.get_instance().disassemble_args(client_id, args, real_args)

            real_kwargs = {}
            PocketManager.get_instance().disassemble_kwargs(client_id, kwargs, real_kwargs)

            real_kwargs['input_shape'] = tuple(real_kwargs['input_shape'])

            model = tf.keras.applications.MobileNetV2(*real_args, **real_kwargs) ###
        except Exception as e:
            import inspect
            from inspect import currentframe, getframeinfo
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': inspect.stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, model)
            PocketManager.get_instance().add_built_model(name='mobilenetv2', model=model)
            return ReturnValue.OK.value, TFDataType.Model(name='mobilenetv2',
                                                          obj_id=id(model)).to_dict()
        finally:
            pass

    @staticmethod
    def tf_keras_applications_ResNet50(client_id, args, **kwargs):
        try:
            PocketManager.get_instance().dict_clientid_to_modelname[client_id]='resnet50'
            if 'resnet50' in PocketManager.get_instance().model_dict:
                model = PocketManager.get_instance().model_dict['resnet50']
                PocketManager.get_instance().add_object_to_per_client_store(client_id, model)
                return ReturnValue.OK.value, TFDataType.Model(name='resnet50',
                                                            obj_id=id(model),
                                                            already_built=True).to_dict()

            real_args = []
            PocketManager.get_instance().disassemble_args(client_id, args, real_args)

            real_kwargs = {}
            PocketManager.get_instance().disassemble_kwargs(client_id, kwargs, real_kwargs)

            real_kwargs['input_shape'] = tuple(real_kwargs['input_shape'])

            model = tf.keras.applications.ResNet50(*real_args, **real_kwargs) ###
        except Exception as e:
            import inspect
            from inspect import currentframe, getframeinfo
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': inspect.stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, model)
            PocketManager.get_instance().add_built_model(name='resnet50', model=model)
            return ReturnValue.OK.value, TFDataType.Model(name='resnet50',
                                                          obj_id=id(model)).to_dict()
        finally:
            pass

    @staticmethod
    def tf_keras_preprocessing_image_img__to__array(client_id, img, data_format=None, dtype=None):
        try:
            img = PocketManager.get_instance().get_real_object_with_mock(client_id, img)
            array = tf.keras.preprocessing.image.img_to_array(img=img, data_format=data_format, dtype=dtype) ###
        except Exception as e:
            import inspect
            from inspect import currentframe, getframeinfo
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': inspect.stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, array)
            return ReturnValue.OK.value, TFDataType.Tensor(name=None,
                                                           obj_id=id(array),
                                                           shape=array.shape).to_dict()
        finally:
            pass

    @staticmethod
    def tf_keras_applications_resnet50_preprocess__input(client_id, args, **kwargs):
        try:
            real_args = []
            PocketManager.get_instance().disassemble_args(client_id, args, real_args)

            real_kwargs = {}
            PocketManager.get_instance().disassemble_kwargs(client_id, kwargs, real_kwargs)

            tensor = tf.keras.applications.resnet50.preprocess_input(*real_args, **real_kwargs) ###
        except Exception as e:
            import inspect
            from inspect import currentframe, getframeinfo
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': inspect.stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, tensor)
            return ReturnValue.OK.value, TFDataType.Tensor(name=None,
                                                           obj_id=id(tensor),
                                                           shape=tensor.shape.as_list()).to_dict()
        finally:
            pass

    @staticmethod
    def tf_saved__model_load(client_id, export_dir, tags=None):
        try:
            dir = f'/models/imdb_prediction/{export_dir}_bert'
            PocketManager.get_instance().dict_clientid_to_modelname[client_id]=export_dir
            if export_dir in PocketManager.get_instance().model_dict:
                model = PocketManager.get_instance().model_dict[export_dir]
                PocketManager.get_instance().add_object_to_per_client_store(client_id, model)
                return ReturnValue.OK.value, TFDataType.Model(name=export_dir,
                                                            obj_id=id(model),
                                                            already_built=True).to_dict()

            model = tf.saved_model.load(dir, tags=tags) ###
        except Exception as e:
            import inspect
            from inspect import currentframe, getframeinfo
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': inspect.stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, model)
            PocketManager.get_instance().add_built_model(name=export_dir, model=model)
            return ReturnValue.OK.value, TFDataType.Model(name=export_dir,
                                                          obj_id=id(model)).to_dict()
        finally:
            pass

class NumpyServer:
    @staticmethod
    def np_argmax(client_id, a, axis=None, out=None):
        try:
            tensor = PocketManager.get_instance().get_real_object_with_mock(client_id, a)
            argmax = np.argmax(tensor, axis, out).item()
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            debug(tb)
            from inspect import currentframe, getframeinfo, stack
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': stack()[0][3]}
        else:
            return ReturnValue.OK.value, argmax
        finally:
            pass

import tensorflow_hub as hub
class HubServer:
    @staticmethod
    def hub_load(client_id, handle, tags=None, options=None):
        try:
            model_name = handle.split('/')[4]
            if model_name in PocketManager.get_instance().model_dict:
                model = PocketManager.get_instance().model_dict[model_name]
                PocketManager.get_instance().add_object_to_per_client_store(client_id, model)
                return ReturnValue.OK.value, TFDataType.Model(name=model_name,
                                                            obj_id=id(model),
                                                            already_built=True).to_dict()
            model = hub.load(handle=handle, tags=tags, options=options)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            debug(tb)
            from inspect import currentframe, getframeinfo, stack
            frameinfo = getframeinfo(currentframe())
            return ReturnValue.EXCEPTIONRAISED.value, {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': stack()[0][3]}
        else:
            PocketManager.get_instance().add_object_to_per_client_store(client_id, model)
            PocketManager.get_instance().add_built_model(name=model_name, model=model)
            return ReturnValue.OK.value, TFDataType.Model(name=model_name,
                                                          obj_id=id(model)).to_dict()
        finally:
            pass

tf_function_dict = {
    TFFunctions.LOCALQ_DEBUG: 
    TensorFlowServer.hello,
    TFFunctions.MODEL_EXIST:
    TensorFlowServer.check_if_model_exist,
    TFFunctions.TF_CALLABLE:
    TensorFlowServer.tf_callable,
    TFFunctions.OBJECT_SLICER:
    TensorFlowServer.object_slicer,
    TFFunctions.TF_SHAPE:
    TensorFlowServer.tf_shape,
    TFFunctions.TF_RESHAPE:
    TensorFlowServer.tf_reshape,
    TFFunctions.TENSOR_DIVISION:
    TensorFlowServer.tensor_division,
    # TFFunctions.TENSOR_SHAPE:
    # TensorFlowServer.tensor_shape,
    TFFunctions.TF_CONSTANT:
    TensorFlowServer.tf_constant,
    TFFunctions.TF_SIGMOID:
    TensorFlowServer.tf_sigmoid,

    TFFunctions._NOPTEST:
    TensorFlowServer._noptest,
    TFFunctions._MATMULTEST:
    TensorFlowServer._matmultest,

    TFFunctions.TF_CONFIG_EXPERIMENTAL_LIST__PHYSICAL__DEVICES: 
    TensorFlowServer.tf_config_experimental_list__physical__devices,
    TFFunctions.TF_CONFIG_EXPERIMENTAL_SET__MEMORY__GROWTH: 
    TensorFlowServer.tf_config_experimental_set__memory__growth,
    # TFFunctions.TF_GRAPH_GET__TENSOR__BY__NAME: 
    # TensorFlowServer.tf_Graph_get__tensor__by__name,
    TFFunctions.TF_KERAS_LAYERS_INPUT: 
    TensorFlowServer.tf_keras_layers_Input,
    TFFunctions.TF_KERAS_LAYERS_ZEROPADDING2D: 
    TensorFlowServer.tf_keras_layers_ZeroPadding2D,
    TFFunctions.TF_KERAS_REGULARIZERS_L2: 
    TensorFlowServer.tf_keras_regularizers_l2,
    TFFunctions.TF_KERAS_LAYERS_CONV2D: 
    TensorFlowServer.tf_keras_layers_Conv2D,
    TFFunctions.TF_KERAS_LAYERS_BATCHNORMALIZATION: 
    TensorFlowServer.tf_keras_layers_BatchNormalization,
    TFFunctions.TF_KERAS_LAYERS_LEAKYRELU: 
    TensorFlowServer.tf_keras_layers_LeakyReLU,
    TFFunctions.TF_KERAS_LAYERS_ADD: 
    TensorFlowServer.tf_keras_layers_Add,
    TFFunctions.TF_KERAS_MODEL: 
    TensorFlowServer.tf_keras_Model,
    TFFunctions.TF_KERAS_LAYERS_LAMBDA: 
    TensorFlowServer.tf_keras_layers_Lambda,
    TFFunctions.TF_KERAS_LAYERS_UPSAMPLING2D: 
    TensorFlowServer.tf_keras_layers_UpSampling2D,
    TFFunctions.TF_KERAS_LAYERS_CONCATENATE: 
    TensorFlowServer.tf_keras_layers_Concatenate,
    TFFunctions.TF_IMAGE_DECODE__IMAGE:
    TensorFlowServer.tf_image_decode__image,
    TFFunctions.TF_EXPAND__DIMS:
    TensorFlowServer.tf_expand__dims,
    TFFunctions.TF_IMAGE_RESIZE:
    TensorFlowServer.tf_image_resize,
    TFFunctions.TF_KERAS_APPLICATIONS_MOBILENETV2:
    TensorFlowServer.tf_keras_applications_MobileNetV2,
    TFFunctions.TF_KERAS_APPLICATIONS_RESNET50:
    TensorFlowServer.tf_keras_applications_ResNet50,
    TFFunctions.TF_KERAS_PREPROCESSING_IMAGE_IMG__TO__ARRAY:
    TensorFlowServer.tf_keras_preprocessing_image_img__to__array,
    TFFunctions.TF_KERAS_APPLICATIONS_RESNET50_PREPROCESS__INPUT:
    TensorFlowServer.tf_keras_applications_resnet50_preprocess__input,
    TFFunctions.TF_SAVED__MODEL_LOAD:
    TensorFlowServer.tf_saved__model_load,

    TFFunctions.TF_MODEL_LOAD_WEIGHTS:
    TensorFlowServer.model_load_weights,

    TFFunctions.NP_ARGMAX:
    NumpyServer.np_argmax,

    TFFunctions.HUB_LOAD:
    HubServer.hub_load,
}

IN_GRAPH = {    
    TFFunctions.LOCALQ_DEBUG,
    TFFunctions.MODEL_EXIST,
    TFFunctions.TF_CALLABLE,
    TFFunctions.OBJECT_SLICER,
    TFFunctions.TF_SHAPE,
    TFFunctions.TF_RESHAPE,
    TFFunctions.TENSOR_DIVISION,

    TFFunctions.TF_CONFIG_EXPERIMENTAL_LIST__PHYSICAL__DEVICES, 
    TFFunctions.TF_CONFIG_EXPERIMENTAL_SET__MEMORY__GROWTH, 
    TFFunctions.TF_KERAS_LAYERS_INPUT, 
    TFFunctions.TF_KERAS_LAYERS_ZEROPADDING2D, 
    TFFunctions.TF_KERAS_REGULARIZERS_L2, 
    TFFunctions.TF_KERAS_LAYERS_CONV2D, 
    TFFunctions.TF_KERAS_LAYERS_BATCHNORMALIZATION, 
    TFFunctions.TF_KERAS_LAYERS_LEAKYRELU, 
    TFFunctions.TF_KERAS_LAYERS_ADD, 
    TFFunctions.TF_KERAS_MODEL, 
    TFFunctions.TF_KERAS_LAYERS_LAMBDA, 
    TFFunctions.TF_KERAS_LAYERS_UPSAMPLING2D, 
    TFFunctions.TF_KERAS_LAYERS_CONCATENATE, 
    TFFunctions.TF_IMAGE_DECODE__IMAGE,
    TFFunctions.TF_EXPAND__DIMS,
    TFFunctions.TF_IMAGE_RESIZE,
    TFFunctions.TF_KERAS_APPLICATIONS_MOBILENETV2,

    TFFunctions.TF_MODEL_LOAD_WEIGHTS,

    TFFunctions.NP_ARGMAX
}

class ResourceMoveRequest:
    class Command(Enum):
        ADD         = 1
        GIVEBACK    = 2

    def __init__(self, command, client, mem, cfs_quota_us, cfs_period_us, sync=False):
        self.command = command
        self.client_id = client
        self.memory = int(mem)
        self.cfs_quota_us = int(cfs_quota_us)
        self.cfs_period_us = int(cfs_period_us)
        self.sync = sync
        if sync:
            debug(f'{command} request_synced')
            self.done = Event()

class PocketManager:
    universal_key = 0x1001 # key for message queue
    __instance = None

    @staticmethod
    def get_instance():
        if PocketManager.__instance == None:
            PocketManager()

        return PocketManager.__instance


    def __init__(self):
        if PocketManager.__instance != None:
            raise Exception('Singleton instance exists already!')

        self.gq = MessageQueue(PocketManager.universal_key, IPC_CREX)
        self.gq_thread = Thread(target=self.pocket_new_connection)
        self.handle_clients_thread = Thread(target=self.pocket_serving_client)
        self.queues_dict = {}
        self.per_client_object_store = {}
        self.model_dict = {}
        self.shmem_dict = {}
        self.fe_to_pid = {}
        self.dict_modelname_to_session = {} 
        self.dict_clientid_to_modelname = {} # todo - clean up @ detach

        self.resource_move_queue = Queue()
        PocketManager.__instance = self
        # self.executor = ThreadPoolExecutor(10)
        self.futures = {} # todo - clean up @ detach

        # self.default_session = tf.compat.v1.Session(graph=tf.Graph())

        self.graph_build_in_progress = False

    def start(self):
        self.gq_thread.daemon = True
        self.gq_thread.start()

        # self resource moving
        self.rsrc_mgr_thread = Thread(target=self.handle_resource_move_request) # todo: remove
        self.rsrc_mgr_thread.daemon=True
        self.rsrc_mgr_thread.start()

        self.handle_clients_thread.daemon = True
        self.handle_clients_thread.start()
        self.handle_clients_thread.join()
        self.gq_thread.join()

    def handle_resource_move_request(self): #@@@
        while True:
            request = self.resource_move_queue.get()
            client_id = request.client_id
            mem = request.memory
            cfs_quota_us = request.cfs_quota_us
            cfs_period_us = request.cfs_period_us
            # debug(request.__dict__)
            try: 
                if  request.command == ResourceMoveRequest.Command.ADD:
                    # sleep(ADD_INTERVAL)
                    Utils.add_resource(client_id, mem, cfs_quota_us, cfs_period_us)
                elif request.command == ResourceMoveRequest.Command.GIVEBACK:
                    # sleep(DEDUCT_INTERVAL)
                    Utils.deduct_resource(client_id, mem, cfs_quota_us, cfs_period_us)

                if request.sync:
                    # debug('sync request!!!!!!!')
                    request.done.set()
                else:
                    # debug('request not synced!!!!!!!')
                    pass
            except OSError as e:
                print(repr(e))
                print(e)

    def pocket_new_connection(self):
        from time import time
        while True:
            raw_msg, raw_type = self.gq.receive(block=True, type=CLIENT_TO_SERVER)
            args_dict = json.loads(raw_msg)
            raw_type = args_dict['raw_type']
        
            # debug('misun>>', args_dict)
            # debug(hex(raw_type))

            type = PocketControl(raw_type)
            reply_type = raw_type | 0x40000000
            if type == PocketControl.CONNECT:
                # debug('>>>conn')

                client_id = args_dict.get('client_id')
                self.add_client_queue(client_id, args_dict['key'])
                self.per_client_object_store[client_id] = {}

                mem = args_dict.get('mem')
                cfs_quota_us = args_dict.get('cfs_quota_us')
                cfs_period_us =  args_dict.get('cfs_period_us')
                Utils.add_resource(client_id, mem, cfs_quota_us, cfs_period_us)
                self.send_ack_to_client(client_id)
                self.fe_to_pid[client_id] = args_dict.get('pid')

                self.shmem_dict[client_id] = SharedMemoryChannel(client_id)
            elif type == PocketControl.DISCONNECT:
                # debug('>>>detach')
                client_id = args_dict.get('client_id')
                its_lq = self.queues_dict.pop(client_id)
                self.per_client_object_store.pop(client_id, None)
                self.shmem_dict.pop(client_id, None)

                self.dict_clientid_to_modelname.pop(client_id, None)
                self.futures.pop(client_id, None)
                self.fe_to_pid.pop(client_id)

                # if args_dict['client_id'] in _matmultest_dict: ## test_code
                #     matrices = _matmultest_dict.pop(args_dict['client_id'])
                #     del matrices
                    # import ctypes
                    # libmatmul = ctypes.CDLL('/root/tfrpc/server/test/libmatmul.so')
                    # libmatmul.free_mem.argtypes = [ctypes.c_void_p]
                    # libmatmul.free_mem.restype = None
                    # for matrix in matrices:
                    #     libmatmul.free_mem(matrix)


                gc.collect()

                mem = args_dict.get('mem')
                cfs_quota_us = args_dict.get('cfs_quota_us')
                cfs_period_us =  args_dict.get('cfs_period_us')
                print('>>>>>>', mem, cfs_quota_us)
                Utils.deduct_resource(client_id, mem, cfs_quota_us, cfs_period_us)
                
                return_dict = {'result': ReturnValue.OK.value}

                return_byte_obj = json.dumps(return_dict)
                its_lq.send(return_byte_obj, type = reply_type)
            elif type == PocketControl.START_BUILD_GRAPH:
                debug('START BUILD')
                client_id = args_dict['client_id']
                if self.graph_build_in_progress == True:
                    return_dict = {'result': ReturnValue.ERROR.value, 'message': 'graph_build already in progress'}
                else:
                    return_dict = {'result': ReturnValue.OK.value, 'message': 'build start!'}
                    self.graph_build_in_progress = True
                    self.graph_build_owner = client_id

                return_byte_obj = json.dumps(return_dict)
                self.queues_dict[client_id].send(return_byte_obj, block=True, type=reply_type)
            elif type == PocketControl.END_BUILD_GRAPH:
                debug('END BUILD')
                client_id = args_dict['client_id']
                if self.graph_build_in_progress == True:
                    return_dict = {'result': ReturnValue.OK.value, 'message': 'build end!'}
                    self.graph_build_in_progress = False
                    self.graph_build_owner = None
                else:
                    return_dict = {'result': ReturnValue.ERROR.value, 'message': 'graph_build not in progress'}

                return_byte_obj = json.dumps(return_dict)
                self.queues_dict[client_id].send(return_byte_obj, block=True, type=reply_type)

            elif type == PocketControl.HELLO:
                return_dict = {'result': ReturnValue.OK.value, 'message': args_dict['message']}
                return_byte_obj = json.dumps(return_dict)
                self.gq.send(return_byte_obj, type=reply_type)
                
            sleep(GLOBAL_SLEEP)

    def pocket_serving_client(self):
        while True:
            for client_id, queue in self.queues_dict.copy().items():
                try:
                    if client_id in self.futures and not self.futures[client_id].done():
                        continue
                    raw_msg, _ = queue.receive(block=False, type=CLIENT_TO_SERVER)

                    args_dict = json.loads(raw_msg)

                    # if self.graph_build_in_progress and client_id == self.graph_build_owner:
                    #     self.worker_naive(client_id, queue, args_dict)
                    # else:
                    self.worker_name(client_id, queue, args_dict)
                    # self.futures[client_id] = self.executor.submit(self.worker_naive, client_id, queue, args_dict)
                    # self.futures[client_id] = self.executor.submit(self.worker_name, client_id, queue, args_dict)
                    # self.worker_naive(client_id, queue, args_dict)
                    
                except BusyError as err:
                    pass
                # sleep(LOCAL_SLEEP)

    def worker_naive(self, client_id, queue, args_dict):
        raw_type = args_dict.pop('raw_type')

        function_type = TFFunctions(raw_type)
        reply_type = raw_type | 0x40000000

        # debug(function_type, client_id, args_dict)
        client_id = args_dict.pop('client_id')
        mem = args_dict.pop('mem')
        cfs_quota_us = args_dict.pop('cfs_quota_us')
        cfs_period_us =  args_dict.pop('cfs_period_us')
        
        Utils.add_resource(client_id, mem, cfs_quota_us, cfs_period_us)
        result, ret = tf_function_dict[function_type](client_id, **args_dict)
        Utils.deduct_resource(client_id, mem, cfs_quota_us, cfs_period_us)

        print(f'>>>>>>>>>>>>>time = {(t2-t1) + (t4-t3)}')
        return_dict = {'result': result}
        if result == ReturnValue.OK.value:
            return_dict.update({'actual_return_val': ret})
        else:
            return_dict.update(ret)
        return_byte_obj = json.dumps(return_dict)

        queue.send(return_byte_obj, type = reply_type)

    def worker_name(self, client_id, queue, args_dict):
        raw_type = args_dict.pop('raw_type')

        function_type = TFFunctions(raw_type)
        reply_type = raw_type | 0x40000000

        # debug(function_type, client_id, args_dict)
        client_id = args_dict.pop('client_id')
        mem = args_dict.pop('mem')
        cfs_quota_us = args_dict.pop('cfs_quota_us')
        cfs_period_us =  args_dict.pop('cfs_period_us')
        # debug('>>>func')

        # from time import time       ## test_code
        # t1 = time()
        # Utils.add_resource_daemon(client_id, mem, cfs_quota_us, cfs_period_us)
        # t2 = time()

        Utils.add_resource(client_id, mem, cfs_quota_us, cfs_period_us)

        if client_id in self.dict_clientid_to_modelname:
            model_name = self.dict_clientid_to_modelname[client_id]
            with tf.name_scope(model_name) as scope:
                result, ret = tf_function_dict[function_type](client_id, **args_dict)
        else:
            result, ret = tf_function_dict[function_type](client_id, **args_dict)

        Utils.deduct_resource(client_id, mem, cfs_quota_us, cfs_period_us)

        # ## test_code
        # t3 = time()
        # Utils.deduct_resource_daemon(client_id, mem, cfs_quota_us, cfs_period_us)
        # t4 = time()
        # debug(f'resource_reallocation={(t2-t1) + (t4-t3)}')

        return_dict = {'result': result}
        if result == ReturnValue.OK.value:
            return_dict.update({'actual_return_val': ret})
        else:
            return_dict.update(ret)
        return_byte_obj = json.dumps(return_dict)

        queue.send(return_byte_obj, type = reply_type)


    # def worker(self, client_id, queue, args_dict):
    #     if client_id in self.dict_clientid_to_modelname:
    #         model_name = self.dict_clientid_to_modelname[client_id]
    #         graph = self.dict_modelname_to_session[model_name]
    #     else:
    #         graph = self.default_graph
    #     try: 
    #         raw_type = args_dict.pop('raw_type')

    #         function_type = TFFunctions(raw_type)
    #         reply_type = raw_type | 0x40000000

    #         # debug(function_type, client_id, args_dict)
    #         granularity = args_dict.pop('granularity', 'conn')
    #         if granularity == 'func':
    #             client_id = args_dict.pop('client_id')
    #             mem = args_dict.pop('mem')
    #             cfs_quota_us = args_dict.pop('cfs_quota_us')
    #             cfs_period_us =  args_dict.pop('cfs_period_us')
    #             Utils.add_resource(client_id, mem, cfs_quota_us, cfs_period_us)

    #         if function_type in IN_GRAPH:
    #             t1 = time()
    #             with graph.as_default():
    #                 t2 = time()
    #                 result, ret = tf_function_dict[function_type](client_id, **args_dict)
    #                 t3 = time()
    #             t4 = time()
    #             debug(f'{function_type.name}: {(t2-t1)*1000:.6f}, {(t3-t2)*1000:.6f}, {(t4-t1)*1000:.6f}')
    #         else:
    #             # tf.config.experimental_run_functions_eagerly(True)
    #             result, ret = tf_function_dict[function_type](client_id, **args_dict)
                
    #         if granularity == 'func':
    #             Utils.deduct_resource(client_id, mem, cfs_quota_us, cfs_period_us)
    #         return_dict = {'result': result}
    #         if result == ReturnValue.OK.value:
    #             return_dict.update({'actual_return_val': ret})
    #         else:
    #             return_dict.update(ret)
    #         # debug(f'\033[91mreturn_dict={return_dict}\033[0m')
    #         return_byte_obj = json.dumps(return_dict)

    #         queue.send(return_byte_obj, type = reply_type)

    #     except Exception as e:
    #         import traceback
    #         tb = traceback.format_exc()
    #         debug(tb)
    #         from inspect import currentframe, getframeinfo, stack
    #         frameinfo = getframeinfo(currentframe())
    #         exception =  {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': stack()[0][3]}
    #         debug(f'exception={exception}')

    def worker_graph(self, client_id, queue, args_dict):
        if client_id in self.dict_clientid_to_modelname:
            model_name = self.dict_clientid_to_modelname[client_id]
            graph = self.dict_modelname_to_session[model_name]
        else:
            graph = self.default_graph
        try: 
            raw_type = args_dict.pop('raw_type')

            function_type = TFFunctions(raw_type)
            reply_type = raw_type | 0x40000000

            # debug(function_type, client_id, args_dict)
            # granularity = args_dict.pop('granularity', 'conn')
            # if granularity == 'func':
            client_id = args_dict.pop('client_id')
            mem = args_dict.pop('mem')
            cfs_quota_us = args_dict.pop('cfs_quota_us')
            cfs_period_us =  args_dict.pop('cfs_period_us')
            Utils.add_resource(client_id, mem, cfs_quota_us, cfs_period_us)

            if function_type in IN_GRAPH:
                t1 = time()
                with graph.as_default():
                    t2 = time()
                    result, ret = tf_function_dict[function_type](client_id, **args_dict)
                    t3 = time()
                t4 = time()
                debug(f'{function_type.name}: {(t2-t1)*1000:.6f}, {(t3-t2)*1000:.6f}, {(t4-t1)*1000:.6f}')
            else:
                # tf.config.experimental_run_functions_eagerly(True)
                result, ret = tf_function_dict[function_type](client_id, **args_dict)
                
            # if granularity == 'func':
            Utils.deduct_resource(client_id, mem, cfs_quota_us, cfs_period_us)
            return_dict = {'result': result}
            if result == ReturnValue.OK.value:
                return_dict.update({'actual_return_val': ret})
            else:
                return_dict.update(ret)
            # debug(f'\033[91mreturn_dict={return_dict}\033[0m')
            return_byte_obj = json.dumps(return_dict)

            queue.send(return_byte_obj, type = reply_type)

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            debug(tb)
            from inspect import currentframe, getframeinfo, stack
            frameinfo = getframeinfo(currentframe())
            exception =  {'exception': e.__class__.__name__, 'message': str(e), 'filename':frameinfo.filename, 'lineno': frameinfo.lineno, 'function': stack()[0][3]}
            debug(f'exception={exception}')

    def add_client_queue(self, client_id, key):
        client_queue = MessageQueue(key)
        self.queues_dict[client_id] = client_queue

    def send_ack_to_client(self, client_id):
        return_dict = {'result': ReturnValue.OK.value, 'message': 'you\'re acked!'}
        return_byte_obj = json.dumps(return_dict)
        reply_type = PocketControl.CONNECT.value | 0x40000000

        self.queues_dict[client_id].send(return_byte_obj, block=True, type=reply_type)

    def add_object_to_per_client_store(self, client_id, object):
        self.per_client_object_store[client_id][id(object)] = object

    def get_object_to_per_client_store(self, client_id, obj_id):
        return self.per_client_object_store[client_id][obj_id]

    def get_real_object_with_mock(self, client_id, mock):
        return self.per_client_object_store[client_id][mock['obj_id']]

    def add_built_model(self, name, model):
        self.model_dict[name] = model

    def disassemble_args(self, client_id, args, real_args):
        for index, elem in enumerate(args):
            real_args.append(None)
            if type(elem) in [list, tuple]:
                real_args[index] = []
                self.disassemble_args(client_id, elem, real_args[index])
            elif type(elem) is dict and 'obj_id' not in elem: # nested dictionary?
                if '_typename' in elem and elem['_typename'] == 'NPArray': #ndarray
                    length = elem['contents_length']
                    dtype = elem['dtype']
                    shape = elem['shape']
                    real_args[index] = np.frombuffer(self.shmem_dict[client_id].read(length), dtype).reshape(shape)
                else:
                    real_args[index] = {}
                    self.disassemble_kwargs(client_id, elem, real_args[index])
            elif type(elem) in (int, float, bool, str, bytes, bytearray):
                real_args[index] = elem
            else:
                real_args[index] = self.get_real_object_with_mock(client_id, elem)

    def disassemble_kwargs(self, client_id, kwargs, real_kwargs):
        for key, value in kwargs.items():
            real_kwargs[key] = None
            if type(value) in [list, tuple]:
                real_kwargs[key] = []
                self.disassemble_args(client_id, value, real_kwargs[key])
            elif type(value) is dict and 'obj_id' not in value: # # nested dictionary?
                if '_typename' in value and value['_typename'] == 'NPArray': #ndarray
                    length = value['contents_length']
                    dtype = value['dtype']
                    shape = value['shape']
                    real_kwargs[key] = np.frombuffer(self.shmem_dict[client_id].read(length), dtype).reshape(shape)
                else:
                    real_kwargs[key] = {}
                    self.disassemble_kwargs(client_id, value, real_kwargs[key])
            elif type(value) in (int, float, bool, str, bytes, bytearray):
                real_kwargs[key] = value
            else:
                real_kwargs[key] = self.get_real_object_with_mock(client_id, value)
