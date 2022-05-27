import subprocess
import sys, os
import gc
import json
# import tensorflow as tf
import numpy as np
from absl import flags
from absl.flags import FLAGS
from enum import Enum
from queue import Queue
import math
# from ctypes import CDLL
# from ctypes import c_void_p, byref, cast, POINTER, c_char, c_size_t, c_int
# from ctypes.util import find_library
from imghdr import what
# import tensorflow_text

from time import sleep, time
from sysv_ipc import MessageQueue, IPC_CREX, BusyError
from threading import Thread, Lock, Event
from threading import Semaphore as pySem
# from concurrent.futures import ThreadPoolExecutor

from pocket_tf_if import PocketControl, TFFunctions, ReturnValue, TFDataType, CLIENT_TO_SERVER, SERVER_TO_CLIENT, SharedMemoryChannel
os.chdir('/root/yolov3-tf2')
# LIBC = CDLL(find_library('c'))

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
    def measure_resource_usage():
        stat_dict = {}
        with open('/sys/fs/cgroup/cpuacct/cpuacct.usage') as f:
            stat_dict['cputime.total'] = f.read()
        with open('/sys/fs/cgroup/cpuacct/cpuacct.usage_sys') as f:
            stat_dict['cputime.sys'] = f.read()
        with open('/sys/fs/cgroup/cpuacct/cpuacct.usage_user') as f:
            stat_dict['cputime.user'] = str(int(stat_dict['cputime.total']) - int(stat_dict['cputime.sys']))
        with open('/sys/fs/cgroup/memory/memory.max_usage_in_bytes') as f:
            stat_dict['memory.max_usage'] = f.read()
        with open('/sys/fs/cgroup/memory/memory.memsw.max_usage_in_bytes') as f:
            stat_dict['memory.memsw.max_usage'] = f.read()
        with open('/sys/fs/cgroup/memory/memory.failcnt') as f:
            stat_dict['memory.failcnt'] = f.read()
        with open('/sys/fs/cgroup/memory/memory.stat') as f:
            for line in f:
                if 'total_pgfault' in line:
                    value = line.split()[-1]
                    stat_dict['memory.stat.pgfault'] = value
                elif 'total_pgmajfault' in line:
                    value = line.split()[-1]
                    stat_dict['memory.stat.pgmajfault'] = value
        return stat_dict

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
                with open('/sys/fs/cgroup/memory/memory.memsw.limit_in_bytes', 'w') as be_swap_limit:
                    be_swap_limit.write(str(be_mem_int*4).strip())

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

        fe_mem_current_limit = Utils.get_memory_limit(client_id)
        fe_mem_int = fe_mem_current_limit - mem
        fe_cfs_quota, fe_cfs_period = Utils.get_cpu_limit(client_id)
        fe_cpu_int = fe_cfs_quota - cfs_quota_us

        be_mem_current_limit = Utils.get_memory_limit()
        be_mem_int = be_mem_current_limit + mem
        be_cfs_quota, be_cfs_period = Utils.get_cpu_limit()
        be_cpu_int = be_cfs_quota + cfs_quota_us

        memory_transferred, cpu_transferred = 0, 0

        # debug(f'old-->cpu={Utils.get_cpu_limit()}) + {cfs_quota_us}, mem={Utils.get_memory_limit()} + {mem}')

        if mem != 0:
            # Checks if memory limit to be < current usage.
            fe_mem_current_usage = Utils.get_memory_usage(client_id)
            how_much_reduce_available = fe_mem_current_limit - fe_mem_current_usage
            how_much_reduce_required = mem
            # debug(how_much_reduce_available, how_much_reduce_required, fe_mem_current_limit, mem)
            # if fe_mem_int < fe_mem_current_usage:
            if how_much_reduce_available < how_much_reduce_required:
                mem = how_much_reduce_available * 0.5
                fe_mem_int = fe_mem_current_limit - mem
                be_mem_int = be_mem_current_limit + mem
                # debug(fe_mem_int)
                # debug(Utils.get_memory_usage(client_id))
            else:
                try:
                    with open(f'/cg/memory/docker/{client_id}/memory.limit_in_bytes', 'w') as fe_limit:
                        fe_limit.write(str(fe_mem_int).strip())
                    # FE swap space does not need to adjusted.. but leave below.
                    # with open(f'/cg/memory/docker/{client_id}/memory.memsw.limit_in_bytes', 'w') as fe_swap_limit:
                    #     try:
                    #         fe_swap_limit.write(str(fe_mem_int*4).strip())
                    #     except:
                    #         raise Exception('OutOfMemory')

                    with open('/sys/fs/cgroup/memory/memory.memsw.limit_in_bytes', 'w') as be_swap_limit:
                        be_swap_limit.write(str(be_mem_int*4).strip())
                    with open('/sys/fs/cgroup/memory/memory.limit_in_bytes', 'w') as be_limit:
                        be_limit.write(str(be_mem_int).strip())
                    memory_transferred = mem
                except Exception as e:
                    memory_transferred = False
                    debug(repr(e), e)

        if cfs_quota_us != 0:
            try:
                with open(f'/cg/cpu/docker/{client_id}/cpu.cfs_quota_us', 'w') as cfs_quota_us_f:
                    cfs_quota_us_f.write(str(fe_cpu_int).strip())
                with open('/sys/fs/cgroup/cpu/cpu.cfs_quota_us', 'w') as cfs_quota_us_f:
                    cfs_quota_us_f.write(str(be_cpu_int).strip())
                cpu_transferred = cfs_quota_us
            except Exception as e:
                cpu_transferred = cfs_quota_us
                debug(repr(e), e)

        MEM_SEM.release()
        CPU_SEM.release()

        return memory_transferred, cpu_transferred

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

# yolo_anchors = np.array([(10, 13), (16, 30), (33, 23), (30, 61), (62, 45),
#                          (59, 119), (116, 90), (156, 198), (373, 326)],
#                         np.float32) / 416
# yolo_anchor_masks = np.array([[6, 7, 8], [3, 4, 5], [0, 1, 2]])

# # but don't delete
# flags.DEFINE_integer('yolo_max_boxes', 100,
#                      'maximum number of boxes per image')
# flags.DEFINE_float('yolo_iou_threshold', 0.5, 'iou threshold')
# flags.DEFINE_float('yolo_score_threshold', 0.5, 'score threshold')


def stack_trace():
    import traceback
    traceback.print_tb()
    traceback.print_exception()
    traceback.print_stack()

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

tf_function_dict = {
    TFFunctions.LOCALQ_DEBUG: 
    TensorFlowServer.hello,
    TFFunctions._NOPTEST:
    TensorFlowServer._noptest,
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

        # # self resource moving
        # self.rsrc_mgr_thread = Thread(target=self.handle_resource_move_request) # todo: remove
        # self.rsrc_mgr_thread.daemon=True
        # self.rsrc_mgr_thread.start()

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

                self.add_client_queue(args_dict['client_id'], args_dict['key'])
                self.per_client_object_store[args_dict['client_id']] = {}

                client_id = args_dict.get('client_id')
                mem = args_dict.get('mem')
                cfs_quota_us = args_dict.get('cfs_quota_us')
                cfs_period_us =  args_dict.get('cfs_period_us')
                Utils.add_resource(client_id, mem, cfs_quota_us, cfs_period_us)
                self.send_ack_to_client(args_dict['client_id'])

                self.shmem_dict[args_dict['client_id']] = SharedMemoryChannel(args_dict['client_id'])
            elif type == PocketControl.DISCONNECT:
                # debug('>>>detach')
                its_lq = self.queues_dict.pop(args_dict['client_id'])
                self.per_client_object_store.pop(args_dict['client_id'], None)
                self.shmem_dict.pop(args_dict['client_id'], None)

                self.dict_clientid_to_modelname.pop(args_dict['client_id'], None)
                self.futures.pop(args_dict['client_id'], None)

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

                client_id = args_dict.get('client_id')
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

        # from time import time       ## test_code
        # t1 = time()
        # Utils.add_resource_daemon(client_id, mem, cfs_quota_us, cfs_period_us)
        # t2 = time()

        mem_transfer, cpu_transfer = Utils.add_resource(client_id, mem, cfs_quota_us, cfs_period_us)

        if client_id in self.dict_clientid_to_modelname:
            model_name = self.dict_clientid_to_modelname[client_id]
            with tf.name_scope(model_name) as scope:
                result, ret = tf_function_dict[function_type](client_id, **args_dict)
        else:
            result, ret = tf_function_dict[function_type](client_id, **args_dict)

        Utils.deduct_resource(client_id, mem_transfer, cpu_transfer, cfs_period_us)

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
