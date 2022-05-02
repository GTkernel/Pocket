import json
import sys, os
# sys.path.insert(0, os.path.abspath('tfrpc/client'))
# from tfrpc.client.pocket_tf_if import POCKET_CLIENT
from types import FunctionType
from inspect import getsourcelines
import socket
from sysv_ipc import MessageQueue, IPC_CREX
from pocket_tf_if import NPArray, TFFunctions, PocketControl, ReturnValue, CLIENT_TO_SERVER, TFDataType, TFDtypes, SharedMemoryChannel, ResizeMethod, POCKET_CLIENT
from time import sleep, time
from collections import namedtuple


import numpy as np

def debug(*args):
    class bcolors:
        HEADER = '\033[95m'
        OKBLUE = '\033[94m'
        OKCYAN = '\033[96m'
        OKGREEN = '\033[92m'
        WARNING = '\033[93m'
        FAIL = '\033[91m'
        ENDC = '\033[0m'
        BOLD = '\033[1m'
        UNDERLINE = '\033[4m'
    import inspect
    filename = inspect.stack()[1].filename
    lineno = inspect.stack()[1].lineno
    caller = inspect.stack()[1].function
    print(f'debug>> [{bcolors.OKCYAN}{filename}:{lineno}{bcolors.ENDC}, {caller}]', *args)

RSRC_REALLOC_RATIO = float(os.environ.get('RSRC_REALLOC_RATIO', str(0.5)))
POCKETD_SOCKET_PATH = '/tmp/pocketd.sock'

class Utils:
    @staticmethod
    def get_container_id():
        cg = open('/proc/self/cgroup')
        content = cg.readlines()
        for line in content:
            if 'docker' in line:
                cid = line.strip().split('/')[-1]
                # debug(cid)
                return cid

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
    def get_memory_limit():
        with open('/sys/fs/cgroup/memory/memory.limit_in_bytes', 'r') as limit_in_bytes:
            memory_limit = int(limit_in_bytes.read().strip())
        return memory_limit

    @staticmethod
    def get_cpu_limit():
        with open(f'/sys/fs/cgroup/cpu/cpu.cfs_period_us', 'r') as cfs_period_us:
            cpu_denominator = int(cfs_period_us.read().strip())
        with open(f'/sys/fs/cgroup/cpu/cpu.cfs_quota_us', 'r') as cfs_quota_us:
            cpu_numerator = int(cfs_quota_us.read().strip())
        return cpu_numerator/cpu_denominator

    @staticmethod
    def get_cpu_limit2():
        with open(f'/sys/fs/cgroup/cpu/cpu.cfs_period_us', 'r') as cfs_period_us:
            cpu_denominator = int(cfs_period_us.read().strip())
        with open(f'/sys/fs/cgroup/cpu/cpu.cfs_quota_us', 'r') as cfs_quota_us:
            cpu_numerator = int(cfs_quota_us.read().strip())
        return cpu_numerator, cpu_denominator

    @staticmethod
    def how_many_memory_move(ratio=None):
        ratio = RSRC_REALLOC_RATIO if ratio == None else ratio
        with open('/sys/fs/cgroup/memory/memory.limit_in_bytes', 'r') as limit_in_bytes:
            memory_limit = int(limit_in_bytes.read().strip()) * ratio
        return int(memory_limit)

                
    @staticmethod
    def how_many_cpu_move(ratio=None):
        ratio = RSRC_REALLOC_RATIO if ratio == None else ratio

        with open(f'/sys/fs/cgroup/cpu/cpu.cfs_period_us', 'r') as cfs_period_us:
            cpu_denominator = int(cfs_period_us.read().strip())
        with open(f'/sys/fs/cgroup/cpu/cpu.cfs_quota_us', 'r') as cfs_quota_us:
            cpu_numerator = int(cfs_quota_us.read().strip())
        # return (cpu_numerator/cpu_denominator) * RSRC_REALLOC_RATIO, cpu_numerator, cpu_denominator
        return int(cpu_numerator * ratio), cpu_denominator

    # todo: remove
    @staticmethod
    def deduct_resource(pocketd, mem, cpu, cpu_denom):
        mem = Utils.get_memory_limit() - mem
        cpu = (Utils.get_cpu_limit() - cpu) * cpu_denom

        pocketd.set_resource(mem=mem, cfs_quota = cpu)

    @staticmethod
    def move_resource(pocketd, mem, cpu, cpu_denom):
        # mem = Utils.get_memory_limit() - mem
        # cpu = (Utils.get_cpu_limit() - cpu) * cpu_denom

        pocketd.migrate_resource(mem, cpu, cpu_denom)

    @staticmethod
    def return_resource(pocketd, mem, cpu, cpu_denom):
        mem = Utils.get_memory_limit() - mem
        cpu = (Utils.get_cpu_limit() - cpu) * cpu_denom

        pocketd.return_resource(mem, cpu, cpu_denom)

class PocketDaemon:
    def __init__(self):
        # debug('pocketd creation')
        pass

    def make_json(self, sender, command, args_dict):
        tmp_data_to_send = {}
        args_dict['sender'] = sender
        args_dict['command'] = command
        data_to_send = json.dumps(args_dict)
        return data_to_send

    # todo: remove
    def set_resource(self, mem, cfs_quota):
        my_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        my_socket.connect(POCKETD_SOCKET_PATH)
        args_dict = {'sender'   : 'FE',
                     'command'  : 'set_resource',
                     'client'   : PocketMessageChannel.client_id, 
                     'mem'      : mem,
                     'cfs_quota': cfs_quota}
        json_data_to_send = json.dumps(args_dict)
        my_socket.send(json_data_to_send.encode('utf-8'))
        data_received = my_socket.recv(1024)
        my_socket.close()

    def migrate_resource(self, mem, cpu, cpu_denom):
        my_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        my_socket.connect(POCKETD_SOCKET_PATH)
        args_dict = {'sender'   : 'FE',
                     'command'  : 'migrate_resource',
                     'client'   : PocketMessageChannel.client_id, 
                     'be'       : os.getenv('BACKEND_UID'),
                     'mem'      : mem,
                     'cpu'      : cpu,
                     'cpudenom' : cpu_denom}
        json_data_to_send = json.dumps(args_dict)
        my_socket.send(json_data_to_send.encode('utf-8'))
        data_received = my_socket.recv(1024)
        my_socket.close()

    def return_resource(self, mem, cpu, cpu_denom):
        my_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        my_socket.connect(POCKETD_SOCKET_PATH)
        args_dict = {'sender'   : 'FE',
                     'command'  : 'return_resource',
                     'client'   : PocketMessageChannel.client_id, 
                     'be'       : os.getenv('BACKEND_UID'),
                     'mem'      : mem,
                     'cpu'      : cpu,
                     'cpudenom' : cpu_denom}
        json_data_to_send = json.dumps(args_dict)
        my_socket.send(json_data_to_send.encode('utf-8'))
        data_received = my_socket.recv(1024)
        my_socket.close()
    # # def measure_resource(self, container_list):

    # todo: remove
    def daemon_config(self, tmp_args_dict):
        my_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        my_socket.connect(POCKETD_SOCKET_PATH)
        sender = 'CLI'
        command = 'config'
        args_dict = json.dumps(tmp_args_dict)
        json_data_to_send = self.make_json(sender, command, args_dict)
        my_socket.send(json_data_to_send.encode('utf-8'))
        data_received = my_socket.recv(1024)
        # debug(f'data_received={data_received}')
        my_socket.close()
        

class PocketMessageChannel:
    universal_key = 0x1001
    client_id = Utils.get_container_id()
    local_key = int(client_id[:8], 16)
    __instance = None
    FUNC = 1
    CONN = 2

    @staticmethod
    def get_instance():
        if PocketMessageChannel.__instance == None:
            PocketMessageChannel()
        
        return PocketMessageChannel.__instance

    def get_tf_callable(self):
        instance = self
        def delegate_tf_callable(*args):
            ret = instance.tf_callable(*args)
            return ret
        return delegate_tf_callable

    def get_tf_iterable_sliced(self):
        instance = self
        def delegate_tf_data_slicing(mock_dict, key):
            ret = instance.object_slicer(mock_dict, key)
            return ret
        return delegate_tf_data_slicing

    def get_model_load_weights(self):
        instance = self
        def delegate_model_load_weights(mock_dict, key):
            ret = instance.model_load_weights(mock_dict, key)
            return ret
        return delegate_model_load_weights

    def get_tensor_division(self):
        instance = self
        def delegate_tensor_division(mock_dict, other):
            ret = instance.tensor_division(mock_dict, other)
            return ret
        return delegate_tensor_division

    # def get_shape_getter(self):
    #     instance = self
    #     def delegate_tensor_shape(mock_dict):
    #         ret = instance.tensor_shape(mock_dict)
    #         return ret
    #     return delegate_tensor_shape

    def disassemble_args(self, args, real_args):
        for index, elem in enumerate(args):
            real_args.append(None)
            if type(elem) in [list, tuple]:
                real_args[index] = []
                self.disassemble_args(elem, real_args[index])
            elif type(elem) is dict:
                real_args[index] = {}
                self.disassemble_kwargs(elem, real_args[index])
            else:
                if hasattr(elem, 'to_dict'):
                    real_args[index] = elem.to_dict()

    def disassemble_kwargs(self, kwargs, real_kwargs):
        for key, value in kwargs.items():
            real_kwargs[key] = None
            if type(value) in [list, tuple]:
                real_kwargs[key] = []
                self.disassemble_args(value, real_kwargs[key])
            elif type(value) is dict:
                real_kwargs[key] = {}
                self.disassemble_kwargs(value, real_kwargs[key])
            else:
                if hasattr(value, 'to_dict'):
                    real_kwargs[key] = value.to_dict()

    def parse_policy(self):
        mem_policy = os.environ.get('POCKET_MEM_POLICY', 'func,ratio,0.5').split(',')
        cpu_policy = os.environ.get('POCKET_CPU_POLICY', 'func,ratio,0.5').split(',')
        # mem_policy = os.environ.get('POCKET_MEM_POLICY', 'conn,minimum').split(',')
        # cpu_policy = os.environ.get('POCKET_CPU_POLICY', 'func,minimum').split(',')
        # conn, func
        # mininum,ratio(,0.5),none

        policy_dict = {'mem': {}, 'cpu': {}}

        policy_dict['mem']['granularity']   = mem_policy[0]
        policy_dict['mem']['amount']        = mem_policy[1]
        if mem_policy[1] == 'ratio':
            policy_dict['mem']['ratio']     = float(mem_policy[2])
            policy_dict['mem']['mem']       = Utils.how_many_memory_move(policy_dict['mem']['ratio'])
        elif mem_policy[1] == 'minimum':
            policy_dict['mem']['mem']       = Utils.get_memory_limit() - 200*1024*1024
            # policy_dict['mem']['mem']       = 0
        elif mem_policy[1] == 'none':
            policy_dict['mem']['mem']       = 0


        policy_dict['cpu']['granularity']   = cpu_policy[0]
        policy_dict['cpu']['amount']        = cpu_policy[1]
        if cpu_policy[1] == 'ratio':
            policy_dict['cpu']['ratio']     = float(cpu_policy[2])
            policy_dict['cpu']['cfs_quota_us'], policy_dict['cpu']['cfs_period_us'] = Utils.how_many_cpu_move(policy_dict['cpu']['ratio'])
        elif cpu_policy[1] == 'minimum':
            quota, _ = Utils.get_cpu_limit2()
            policy_dict['cpu']['cfs_period_us'] = 100000
            policy_dict['cpu']['cfs_quota_us']       = 90000
        elif cpu_policy[1] == 'none':
            policy_dict['cpu']['cfs_period_us'] = 100000
            policy_dict['cpu']['cfs_quota_us']       = 0
        return policy_dict

    def __init__(self):
        # attach to global queue
        if PocketMessageChannel.__instance != None:
            raise Exception("Only one channel can be exist.")

        else:
            ## Setns
            from time import time
            t1 = time()
            from ctypes import CDLL
            CLONE_NEWIPC = 0x08000000
            CLONE_NEWPID = 0x20000000
            libc = CDLL('libc.so.6')
            libc.unshare(CLONE_NEWIPC)
            t2 = time()

            self.policy = self.parse_policy()

            self.pocketd = PocketDaemon()
            self.gq = MessageQueue(PocketMessageChannel.universal_key)
            self.shmem = SharedMemoryChannel(key=PocketMessageChannel.client_id, size=1 * (32 + 5 * 1024 * 1024))

            self.CONN_MEMORY_LIMIT_IN_BYTES = 0
            self.CONN_CPU_QUOTA_US = 0
            self.CONN_CPU_PERIOD_US = 100000
            self.FUNC_MEMORY_LIMIT_IN_BYTES = 0
            self.FUNC_CPU_QUOTA_US = 0
            self.FUNC_CPU_PERIOD_US = 100000

            if self.policy['cpu']['granularity'] == 'conn':
                self.CONN_CPU_QUOTA_US = self.policy['cpu']['cfs_quota_us']
                self.CONN_CPU_PERIOD_US = self.policy['cpu']['cfs_period_us']
            elif self.policy['cpu']['granularity'] == 'func':
                self.FUNC_CPU_QUOTA_US = self.policy['cpu']['cfs_quota_us']
                self.FUNC_CPU_PERIOD_US = self.policy['cpu']['cfs_period_us']

            if self.policy['mem']['granularity'] == 'conn':
                self.CONN_MEMORY_LIMIT_IN_BYTES = self.policy['mem']['mem']
            elif self.policy['mem']['granularity'] == 'func':
                self.FUNC_MEMORY_LIMIT_IN_BYTES = self.policy['mem']['mem']

            # string = f'self.CONN_CPU_QUOTA_US={self.CONN_CPU_QUOTA_US}\nself.CONN_CPU_PERIOD_US={self.CONN_CPU_PERIOD_US}\nself.CONN_MEMORY_LIMIT_IN_BYTES={self.CONN_MEMORY_LIMIT_IN_BYTES}\nself.FUNC_CPU_QUOTA_US={self.FUNC_CPU_QUOTA_US}\nself.FUNC_CPU_PERIOD_US={self.FUNC_CPU_PERIOD_US}\nself.FUNC_MEMORY_LIMIT_IN_BYTES={self.FUNC_MEMORY_LIMIT_IN_BYTES}'
            # raise Exception(string)

            t3 = time()
            self.conn(PocketMessageChannel.local_key)
            t4 = time()

            TFDataType.callable_delegator = self.get_tf_callable()
            TFDataType.iterable_slicer = self.get_tf_iterable_sliced()
            TFDataType.Model.load_weights = self.get_model_load_weights()
            TFDataType.Tensor.tensor_division = self.get_tensor_division()
            # TFDataType.Tensor.get_shape = self.get_shape_getter()
            PocketMessageChannel.__instance = self
            t5 = time()
            # print(f'time={t5-t4}, {t4-t3}, {t3-t2}, {t2-t1}')

    # control functions
    # for debugging
    def hello(self, message):
        msg_type = int(PocketControl.HELLO)
        reply_type = msg_type | 0x40000000
        args_dict = {'raw_type': msg_type,
                     'message': message}
        args_json = json.dumps(args_dict)

        self.gq.send(args_json, block=True, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.gq.receive(block=True, type=reply_type)
        
        msg = json.loads(raw_msg)
        # debug(json.dumps(msg, indent=2, sort_keys=True))

    # for connecting
    def conn(self, key):
        # create local queue
        self.lq = MessageQueue(key, IPC_CREX)

        msg_type = int(PocketControl.CONNECT)
        reply_type = msg_type | 0x40000000         

        args_dict = {'client_id'    : PocketMessageChannel.client_id, 
                     'key'          : key,
                     'mem'          : self.CONN_MEMORY_LIMIT_IN_BYTES,
                     'cfs_quota_us' : self.CONN_CPU_QUOTA_US,
                     'cfs_period_us': self.CONN_CPU_PERIOD_US}

        args_dict['raw_type'] = msg_type
        
        args_json = json.dumps(args_dict)

        self.gq.send(args_json, type = CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)
        msg = json.loads(raw_msg)
        # debug(json.dumps(msg, indent=2, sort_keys=True))


    # for disconnecting
    def detach(self):
        msg_type = int(PocketControl.DISCONNECT)
        reply_type = msg_type | 0x40000000
        args_dict = {'client_id'    : PocketMessageChannel.client_id,
                     'key'          : PocketMessageChannel.local_key,
                     'mem'          : self.CONN_MEMORY_LIMIT_IN_BYTES,
                     'cfs_quota_us' : self.CONN_CPU_QUOTA_US,
                     'cfs_period_us': self.CONN_CPU_PERIOD_US}

        # args_dict['granularity'] = self.granularity
        args_dict['raw_type'] = msg_type
        args_dict['tf'] = False
        
        args_json = json.dumps(args_dict)

        self.gq.send(args_json, type = CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)
        self.lq.remove()
        msg = json.loads(raw_msg)
        # Utils.return_resource(self.pocketd, self.FUNC_MEMORY_LIMIT_IN_BYTES, self.FUNC_CPU_QUOTA_US, self.FUNC_CPU_PERIOD_US)

    def start_build_graph(self):
        msg_type = int(PocketControl.START_BUILD_GRAPH)
        reply_type = msg_type | 0x40000000

        args_dict = {'client_id'    : PocketMessageChannel.client_id, 
                     'mem'          : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                     'cfs_quota_us' : self.FUNC_CPU_QUOTA_US,
                     'cfs_period_us': self.FUNC_CPU_PERIOD_US}

        args_dict['raw_type'] = msg_type
        args_dict['granularity'] = self.granularity
        
        args_json = json.dumps(args_dict)

        self.gq.send(args_json, type = CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)
        msg = json.loads(raw_msg)

    def end_build_graph(self):
        msg_type = int(PocketControl.END_BUILD_GRAPH)
        reply_type = msg_type | 0x40000000

        args_dict = {'client_id'    : PocketMessageChannel.client_id, 
                     'mem'          : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                     'cfs_quota_us' : self.FUNC_CPU_QUOTA_US,
                     'cfs_period_us': self.FUNC_CPU_PERIOD_US}

        args_dict['raw_type'] = msg_type
        args_dict['granularity'] = self.granularity
        
        args_json = json.dumps(args_dict)

        self.gq.send(args_json, type = CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)
        msg = json.loads(raw_msg)


    # for debugging    
    def hello_via_lq(self, message):
        msg_type = int(TFFunctions.LOCALQ_DEBUG)
        reply_type = msg_type | 0x40000000
        args_dict = {'message': message}
        args_dict['raw_type'] = msg_type
        
        args_json = json.dumps(args_dict)

        self.lq.send(args_json, block=True, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)
        # debug(json.dumps(msg, indent=2, sort_keys=True))

    def _noptest(self):
        msg_type = int(TFFunctions._NOPTEST)
        reply_type = msg_type | 0x40000000

        args_dict = {}
        args_dict['raw_type'] = msg_type

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        self.convert_object_to_dict(args_dict)
        args_json = json.dumps(args_dict)

        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Tensor(dict=msg.get('actual_return_val', None))
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def _matmultest(self, N):
        msg_type = int(TFFunctions._MATMULTEST)
        reply_type = msg_type | 0x40000000

        args_dict = {'N': N}
        args_dict['raw_type'] = msg_type

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        self.convert_object_to_dict(args_dict)
        args_json = json.dumps(args_dict)

        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Tensor(dict=msg.get('actual_return_val', None))
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'], msg['filename'], msg['function'], msg['lineno'])
        else:
            raise Exception('Invalid Result!')

    def check_if_model_exist(self, model_name):
        msg_type = int(TFFunctions.MODEL_EXIST)
        reply_type = msg_type | 0x40000000
        args_dict = {'model_name': model_name}
        args_dict['raw_type'] = msg_type

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)

        self.lq.send(args_json, block=True, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)
        
        msg = json.loads(raw_msg)
        # debug(json.dumps(msg, indent=2, sort_keys=True))

        if msg['result'] == ReturnValue.OK.value:
            ret = msg.get('actual_return_val', None)
            if ret[1] is not None:
                ret[1] = TFDataType.Model(dict=ret[1])
                return ret
            else:
                return ret
            # return msg.get('actual_return_val', None)
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_callable(self, typename, callable, *args):
        msg_type = int(TFFunctions.TF_CALLABLE)
        reply_type = msg_type | 0x40000000
        args_dict = {'typename': typename, 'callable': callable, 'args': args}
        args_dict['raw_type'] = msg_type
        args_list = list(args)
        args_dict['args'] = args_list

        # if self.granularity == 'func':
        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        self.convert_object_to_dict(old_list=args_list)

        args_json = json.dumps(args_dict)

        # from time import time
        # s = time()
        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)
        # e = time()
        # print(f'time={e-s}')

        msg = json.loads(raw_msg)
        if msg['result'] == ReturnValue.OK.value:
            ret = msg['actual_return_val']
            if type(ret) is list:
                ret_list = [TFDataType.Tensor(dict=item) for item in ret]
                return ret_list
            elif 'shmem' in ret:
                length = ret['shmem']['length']
                returned_dict = {}
                # returned_dict = json.loads(self.shmem.read(length).tobytes()) # optim 1
                return returned_dict
            else:
                ret = TFDataType.Tensor(dict=ret)
                return ret
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'], msg['filename'], msg['function'], msg['lineno'])
        else:
            raise Exception('Invalid Result!')

    def object_slicer(self, mock_dict, key):
        msg_type = int(TFFunctions.OBJECT_SLICER)
        reply_type = msg_type | 0x40000000
        args_dict = {'mock_dict': mock_dict, 'key': key}
        args_dict['raw_type'] = msg_type

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}


        args_json = json.dumps(args_dict)

        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Tensor.make_tensor(dict=msg['actual_return_val'])
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tensor_division(self, mock_dict, other):
        msg_type = int(TFFunctions.TENSOR_DIVISION)
        reply_type = msg_type | 0x40000000
        args_dict = {'mock_dict': mock_dict, 'other': other}
        args_dict['raw_type'] = msg_type

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)

        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Tensor.make_tensor(dict=msg['actual_return_val'])
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')


    # def tensor_shape(self, mock_dict):
    #     msg_type = int(TFFunctions.TENSOR_SHAPE)
    #     reply_type = msg_type | 0x40000000
    #     args_dict = {'mock_dict': mock_dict}
    #     args_dict['raw_type'] = msg_type

    #     args_json = json.dumps(args_dict)

    #     self.lq.send(args_json, type=CLIENT_TO_SERVER)
    #     raw_msg, _ = self.lq.receive(block=True, type=reply_type)

    #     msg = json.loads(raw_msg)

    #     if msg['result'] == ReturnValue.OK.value:
    #         return msg['actual_return_val']
    #     elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
    #         raise Exception(msg['exception'])
    #     else:
    #         raise Exception('Invalid Result!')

    def model_load_weights(self, model, filepath, by_name=False, skip_mismatch=False):
        if model.already_built:
            return

        msg_type = int(TFFunctions.TF_MODEL_LOAD_WEIGHTS)
        reply_type = msg_type | 0x40000000
        args_dict = {'model': model, 'filepath': filepath, 'by_name': by_name, 'skip_mismatch': skip_mismatch}
        args_dict['raw_type'] = msg_type

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        self.convert_object_to_dict(args_dict)
        args_json = json.dumps(args_dict)

        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_shape(self, input, out_type=TFDtypes.tf_dtypes_int32, name=None):
        msg_type = int(TFFunctions.TF_SHAPE)
        reply_type = msg_type | 0x40000000

        args_dict = {'input': input, 'out_type': out_type, 'name': name}
        args_dict['raw_type'] = msg_type

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        self.convert_object_to_dict(args_dict)
        args_json = json.dumps(args_dict)

        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Tensor(dict=msg.get('actual_return_val', None))
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_reshape(self, tensor, shape, name=None):
        msg_type = int(TFFunctions.TF_RESHAPE)
        reply_type = msg_type | 0x40000000

        args_dict = {'tensor': tensor, 'shape': shape, 'name': name}
        # args_dict.update(**kwargs)
        args_dict['raw_type'] = msg_type

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        self.convert_object_to_dict(args_dict)
        args_json = json.dumps(args_dict)

        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Tensor(dict=msg.get('actual_return_val', None))
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_config_experimental_list__physical__devices(self, device_type=None):
        msg_type = int(TFFunctions.TF_CONFIG_EXPERIMENTAL_LIST__PHYSICAL__DEVICES)
        reply_type = msg_type | 0x40000000
        args_dict = {'device_type': device_type}
        args_dict['raw_type'] = msg_type

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}
        
        args_json = json.dumps(args_dict)

        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)
        # debug('tf_config_experimental_list__physical__devices', json.dumps(msg, indent=2, sort_keys=True))

        if msg['result'] == ReturnValue.OK.value:
            return [TFDataType.PhysicalDevice(dict=item) for item in msg['actual_return_val']]
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_config_experimental_set__memory__growth(self, device, enable):
        msg_type = int(TFFunctions.TF_CONFIG_EXPERIMENTAL_SET__MEMORY__GROWTH)
        reply_type = msg_type | 0x40000000
        args_dict = {'device': device, 'enable': enable}
        args_dict['raw_type'] = msg_type

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}
        
        args_json = json.dumps(args_dict)

        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)
        # debug(json.dumps(msg, indent=2, sort_keys=True))

        if msg['result'] == ReturnValue.OK.value:
            return msg['actual_return_val']
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_Graph_get__tensor__by__name(self, name):
        msg_type = int(TFFunctions.TF_GRAPH_GET__TENSOR__BY__NAME)
        reply_type = msg_type | 0x40000000
        args_dict = {'name': name}
        args_dict['raw_type'] = msg_type

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)

        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)
        # debug(json.dumps(msg, indent=2, sort_keys=True))

        if msg['result'] == ReturnValue.OK.value:
            return msg.get('actual_return_val', None)
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_keras_layers_Input(self, shape=None, batch_size=None, name=None, dtype=None, sparse=False, tensor=None, ragged=False, **kwargs):
        msg_type = int(TFFunctions.TF_KERAS_LAYERS_INPUT)
        reply_type = msg_type | 0x40000000

        args_dict = {'shape': shape, 'batch_size': batch_size, 'name': name, 'dtype': dtype, 'sparse': sparse, 'tensor': tensor, 'ragged': ragged}
        args_dict.update(**kwargs)
        args_dict['raw_type'] = msg_type

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)

        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            ret = TFDataType.Tensor(dict=msg.get('actual_return_val', None))
            return ret
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')


    def tf_keras_layers_ZeroPadding2D(self, padding=(1, 1), data_format=None, **kwargs):
        msg_type = int(TFFunctions.TF_KERAS_LAYERS_ZEROPADDING2D)
        reply_type = msg_type | 0x40000000

        args_dict = {'padding': padding, 'data_format': data_format}
        args_dict.update(**kwargs)
        args_dict['raw_type'] = msg_type

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)

        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.ZeroPadding2D(dict=msg.get('actual_return_val', None))
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_keras_regularizers_l2(self, l=0.01):
        msg_type = int(TFFunctions.TF_KERAS_REGULARIZERS_L2) ###
        reply_type = msg_type | 0x40000000

        args_dict = {'l': l} ###
        args_dict['raw_type'] = msg_type

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)

        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)
        # debug(json.dumps(msg, indent=2, sort_keys=True))

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.L2(dict=msg.get('actual_return_val', None)) ###
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_keras_layers_Conv2D(self, filters, kernel_size, strides=(1, 1),
        padding='valid', data_format=None,
        dilation_rate=(1, 1), activation=None, use_bias=True,
        kernel_initializer='glorot_uniform', bias_initializer='zeros',
        kernel_regularizer=None, bias_regularizer=None, activity_regularizer=None,
        kernel_constraint=None, bias_constraint=None, **kwargs):

        msg_type = int(TFFunctions.TF_KERAS_LAYERS_CONV2D) ###
        reply_type = msg_type | 0x40000000

        args_dict = {'filters': filters, 'kernel_size': kernel_size, 'strides': strides, 'padding': padding, 'data_format': data_format, 'dilation_rate': dilation_rate, 'activation': activation, 'use_bias':use_bias, 'kernel_initializer':kernel_initializer, 
        'bias_initializer':bias_initializer,
        'kernel_regularizer':kernel_regularizer, 
        'bias_regularizer':bias_regularizer, 
        'activity_regularizer':activity_regularizer,
        'kernel_constraint':kernel_constraint, 'bias_constraint':bias_constraint} ###
        args_dict.update(**kwargs)
        args_dict['raw_type'] = msg_type
        for key, value in args_dict.copy().items():
            if hasattr(value, 'to_dict'):
                args_dict[key] = value.to_dict()

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)
        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Conv2D(dict=msg.get('actual_return_val', None)) ###
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_keras_layers_BatchNormalization(self,
    axis=-1, momentum=0.99, epsilon=0.001, center=True, scale=True,
    beta_initializer='zeros', gamma_initializer='ones',
    moving_mean_initializer='zeros', moving_variance_initializer='ones',
    beta_regularizer=None, gamma_regularizer=None, beta_constraint=None,
    gamma_constraint=None, renorm=False, renorm_clipping=None, renorm_momentum=0.99,
    fused=None, trainable=True, virtual_batch_size=None, adjustment=None, name=None,
    **kwargs):
        msg_type = int(TFFunctions.TF_KERAS_LAYERS_BATCHNORMALIZATION)
        reply_type = msg_type | 0x40000000

        args_dict = {'axis': axis, 'momentum': momentum, 'epsilon': epsilon, 'center': center, 'scale': scale, 'beta_initializer': beta_initializer, 'gamma_initializer': gamma_initializer, 'moving_mean_initializer':moving_mean_initializer, 'moving_variance_initializer':moving_variance_initializer, 
        'beta_regularizer':beta_regularizer,
        'gamma_regularizer':gamma_regularizer, 
        'beta_constraint':beta_constraint, 
        'gamma_constraint':gamma_constraint,
        'renorm':renorm, 'renorm_clipping':renorm_clipping, 'renorm_momentum': renorm_momentum, 'fused': fused, 'trainable': trainable, 'virtual_batch_size': virtual_batch_size, 'adjustment': adjustment, 'name': name}
        args_dict.update(**kwargs)
        args_dict['raw_type'] = msg_type

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)

        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.BatchNormalization(dict=msg.get('actual_return_val', None))
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_keras_layers_LeakyReLU(self, alpha=0.3, **kwargs):
        msg_type = int(TFFunctions.TF_KERAS_LAYERS_LEAKYRELU)
        reply_type = msg_type | 0x40000000

        args_dict = {'alpha': alpha}
        args_dict.update(**kwargs)
        args_dict['raw_type'] = msg_type

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)

        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.LeakyReLU(dict=msg.get('actual_return_val', None))
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_keras_layers_Add(self, **kwargs):
        msg_type = int(TFFunctions.TF_KERAS_LAYERS_ADD) ###
        reply_type = msg_type | 0x40000000

        args_dict = {} ###
        args_dict.update(**kwargs)
        args_dict['raw_type'] = msg_type
        for key, value in args_dict.copy().items():
            if hasattr(value, 'to_dict'):
                args_dict[key] = value.to_dict()

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)
        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Add(dict=msg.get('actual_return_val', None)) ###
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_keras_Model(self, *args, **kwargs):
        msg_type = int(TFFunctions.TF_KERAS_MODEL) ###
        reply_type = msg_type | 0x40000000

        args_dict = {'args': args} ###
        args_dict.update(**kwargs)
        args_dict['raw_type'] = msg_type

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        self.convert_object_to_dict(args_dict)

        args_json = json.dumps(args_dict)
        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Model(dict=msg.get('actual_return_val', None)) ###
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'], msg['filename'], msg['function'], msg['lineno'])
        else:
            raise Exception('Invalid Result!')

    def tf_keras_layers_Lambda(self, function, output_shape=None, mask=None, arguments=None, **kwargs):
        msg_type = int(TFFunctions.TF_KERAS_LAYERS_LAMBDA) ###
        reply_type = msg_type | 0x40000000

        function, raw_args = self.__get_str_from_lambda(function)
        args_dict = {'function': function, 'output_shape': output_shape, 'mask': mask, 'arguments': arguments} ###
        args_dict.update(**kwargs)
        args_dict['raw_type'] = msg_type

        context = kwargs.get('context', None)
        if context is None:
            raise Exception('context info is needed!')
        context = self.__context_filter(context, function, raw_args)
        function = self.__substitute_closure_vars_with_context(function, context)
        args_dict.pop('context')
        args_dict['function'] = function

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        self.convert_object_to_dict(args_dict)

        args_json = json.dumps(args_dict)
        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Lambda(dict=msg.get('actual_return_val', None)) ###
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_keras_layers_UpSampling2D(self, size=(2, 2), data_format=None, interpolation='nearest', **kwargs):
        msg_type = int(TFFunctions.TF_KERAS_LAYERS_UPSAMPLING2D) ###
        reply_type = msg_type | 0x40000000

        args_dict = {'size':size, 'data_format':data_format} ###
        args_dict.update(**kwargs)
        args_dict['raw_type'] = msg_type
        for key, value in args_dict.copy().items():
            if hasattr(value, 'to_dict'):
                args_dict[key] = value.to_dict()

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)
        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Add(dict=msg.get('actual_return_val', None)) ###
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_keras_layers_Concatenate(self, axis=-1, **kwargs):
        msg_type = int(TFFunctions.TF_KERAS_LAYERS_CONCATENATE) ###
        reply_type = msg_type | 0x40000000

        args_dict = {'axis':axis} ###
        args_dict.update(**kwargs)
        args_dict['raw_type'] = msg_type
        for key, value in args_dict.copy().items():
            if hasattr(value, 'to_dict'):
                args_dict[key] = value.to_dict()

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)
        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Add(dict=msg.get('actual_return_val', None)) ###
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_image_decode__image(self, contents, channels=None, dtype=TFDtypes.tf_dtypes_uint8, name=None, expand_animations=True):
        msg_type = int(TFFunctions.TF_IMAGE_DECODE__IMAGE) ###
        reply_type = msg_type | 0x40000000

        args_dict = {'contents': contents, 'channels': channels, 'dtype': dtype, 'name': name, 'expand_animations': expand_animations} ###
        args_dict['raw_type'] = msg_type
        self.convert_object_to_dict(args_dict)

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)
        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Tensor(dict=msg.get('actual_return_val', None)) ###
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_expand__dims(self, input, axis, name=None):
        msg_type = int(TFFunctions.TF_EXPAND__DIMS) ###
        reply_type = msg_type | 0x40000000

        args_dict = {'input': input, 'axis': axis, 'name': name} ###
        args_dict['raw_type'] = msg_type
        self.convert_object_to_dict(args_dict)

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)
        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Tensor(dict=msg.get('actual_return_val', None)) ###
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_constant(self, value, dtype=None, shape=None, name='Const'):
        msg_type = int(TFFunctions.TF_CONSTANT) ###
        reply_type = msg_type | 0x40000000

        value = ';'.join(value)

        args_dict = {'value': len(value), 'dtype': dtype, 'shape': shape, 'name': name} ###
        args_dict['raw_type'] = msg_type
        self.convert_object_to_dict(args_dict)
        self.shmem.write(contents=bytes(value, 'utf-8'))

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)
        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Tensor(dict=msg.get('actual_return_val', None)) ###
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_sigmoid(self, x, name=None):
        msg_type = int(TFFunctions.TF_SIGMOID) ###
        reply_type = msg_type | 0x40000000

        args_dict = {'x': x, 'name': name} ###
        args_dict['raw_type'] = msg_type
        self.convert_object_to_dict(args_dict)

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)
        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            # return TFDataType.Tensor(dict=msg.get('actual_return_val', None)) ###
            return msg.get('actual_return_val', None) ###
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'], msg['filename'], msg['function'], msg['lineno'])
        else:
            raise Exception('Invalid Result!')

    def tf_image_resize(self, images, size, method=ResizeMethod.BILINEAR, preserve_aspect_ratio=False,
    antialias=False, name=None):
        msg_type = int(TFFunctions.TF_IMAGE_RESIZE) ###
        reply_type = msg_type | 0x40000000

        if type(method) is not str:
            method = method.value

        args_dict = {'images': images, 'size': size, 'method': method, 'preserve_aspect_ratio': preserve_aspect_ratio, 'antialias': antialias, 'name': name} ###
        args_dict['raw_type'] = msg_type
        self.convert_object_to_dict(args_dict)

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)
        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Tensor(dict=msg.get('actual_return_val', None)) ###
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_keras_preprocessing_image_img__to__array(self, img, data_format=None, dtype=None):
        msg_type = int(TFFunctions.TF_KERAS_PREPROCESSING_IMAGE_IMG__TO__ARRAY) ###
        reply_type = msg_type | 0x40000000

        args_dict = {'img': img, 'data_format': data_format, 'dtype': dtype} ###
        args_dict['raw_type'] = msg_type
        self.convert_object_to_dict(args_dict)

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)
        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Tensor(dict=msg.get('actual_return_val', None)) ###
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(f'{msg["exception"]}: {msg["message"]} ({msg["filename"]}:{msg["lineno"]}:{msg["function"]})')
        else:
            raise Exception('Invalid Result!')

    def tf_keras_applications_resnet50_preprocess__input(self, *args, **kwargs):
        msg_type = int(TFFunctions.TF_KERAS_APPLICATIONS_RESNET50_PREPROCESS__INPUT) ###
        reply_type = msg_type | 0x40000000

        args_dict = {'args': args} ###
        args_dict.update(**kwargs)
        args_dict['raw_type'] = msg_type

        self.convert_object_to_dict(args_dict)

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)
        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Tensor(dict=msg.get('actual_return_val', None)) ###
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(f'{msg["exception"]}: {msg["message"]} ({msg["filename"]}:{msg["lineno"]}:{msg["function"]})')
        else:
            raise Exception('Invalid Result!')

    def tf_keras_applications_MobileNetV2(self, *args, **kwargs):
        msg_type = int(TFFunctions.TF_KERAS_APPLICATIONS_MOBILENETV2) ###
        reply_type = msg_type | 0x40000000

        args_dict = {'args': args} ###
        args_dict.update(**kwargs)
        args_dict['raw_type'] = msg_type

        self.convert_object_to_dict(args_dict)

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)
        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Model(dict=msg.get('actual_return_val', None)) ###
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            # debug(msg['message'])
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_keras_applications_ResNet50(self, *args, **kwargs):
        msg_type = int(TFFunctions.TF_KERAS_APPLICATIONS_RESNET50) ###
        reply_type = msg_type | 0x40000000

        args_dict = {'args': args} ###
        args_dict.update(**kwargs)
        args_dict['raw_type'] = msg_type

        self.convert_object_to_dict(args_dict)

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)
        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Model(dict=msg.get('actual_return_val', None)) ###
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            # debug(msg['message'])
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def np_argmax(self, a, axis=None, out=None):
        msg_type = int(TFFunctions.NP_ARGMAX) ###
        reply_type = msg_type | 0x40000000

        args_dict = {'a': a, 'axis': axis, 'out': out} ###
        args_dict['raw_type'] = msg_type
        self.convert_object_to_dict(args_dict)

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)
        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return msg.get('actual_return_val', None) ### integer
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def hub_load(self, handle, tags=None, options=None):
        msg_type = int(TFFunctions.HUB_LOAD) ###
        reply_type = msg_type | 0x40000000

        args_dict = {'handle':handle, 'tags':tags, 'options':options} ###
        args_dict['raw_type'] = msg_type
        self.convert_object_to_dict(args_dict)

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)
        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Model(dict=msg.get('actual_return_val', None)) ###
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'])
        else:
            raise Exception('Invalid Result!')

    def tf_saved__model_load(self, export_dir, tags=None):
        msg_type = int(TFFunctions.TF_SAVED__MODEL_LOAD) ###
        reply_type = msg_type | 0x40000000

        args_dict = {'export_dir':export_dir, 'tags':tags} ###
        args_dict['raw_type'] = msg_type
        self.convert_object_to_dict(args_dict)

        resource = {'client_id'     : PocketMessageChannel.client_id,
                    'mem'           : self.FUNC_MEMORY_LIMIT_IN_BYTES,
                    'cfs_quota_us'  : self.FUNC_CPU_QUOTA_US,
                    'cfs_period_us' : self.FUNC_CPU_PERIOD_US}
        args_dict = {**args_dict, **resource}

        args_json = json.dumps(args_dict)
        self.lq.send(args_json, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)

        msg = json.loads(raw_msg)

        if msg['result'] == ReturnValue.OK.value:
            return TFDataType.Model(dict=msg.get('actual_return_val', None)) ###
        elif msg['result'] == ReturnValue.EXCEPTIONRAISED.value:
            raise Exception(msg['exception'], msg['filename'], msg['function'], msg['lineno'])
        else:
            raise Exception('Invalid Result!')

    def __remove_code_after_lambda(self, string):
        parenthese_cursor = 1
        new_substring = ''
        for index in range(0, len(string)):
            if string[index] == '(':
                parenthese_cursor += 1
                # debug(parenthese_cursor, index, string[index+1:])
            elif string[index] == ')':
                parenthese_cursor -= 1
                # debug(parenthese_cursor, index, string[index+1:])
            elif parenthese_cursor == 1 and string[index] == ',':
                parenthese_cursor -= 1

            if parenthese_cursor is 0:
                new_substring = 'lambda' + string[0:index]
                break
        return new_substring

    def __get_str_from_lambda(self, func):
        func_string = str(getsourcelines(func)[0])
        func_string = func_string.split('lambda', 2)[1]
        raw_args = [elem.strip() for elem in func_string.split(':')[0].split(',')]
        func_string = self.__remove_code_after_lambda(func_string)
        return func_string, raw_args

    def __context_filter(self, context, function, function_param):
        new_context = {}
        for key, value in context.items():
            if key in function and key not in function_param:
                new_context[key] = value

        return new_context

    def __substitute_closure_vars_with_context(self, function, context):
        new_string = function
        for key, value in context.copy().items():
            index = 0
            while index < len(function):
                if function[index:].startswith(key) and \
                   not function[index-1].isalnum() and \
                   not function[index+len(key)].isalnum():
                   substitute = str(value)
                   new_string = function[:index] + function[index:].replace(key, substitute, 1)
                   function = new_string
                index += 1
            function = new_string
        return function



    def convert_object_to_dict(self, old_dict: dict = None, old_list: list = None):
        if old_dict is not None:
            for key, value in old_dict.copy().items():
                datatype = type(value)
                if isinstance(value, TFDataType.Tensor):
                    old_dict[key] = value.to_dict()
                elif datatype is TFDtypes:
                    old_dict[key] = value.value
                elif datatype is list:
                    self.convert_object_to_dict(old_list = value)
                elif datatype is tuple:
                    old_dict[key] = tuple_to_list = list(value)
                    self.convert_object_to_dict(old_list = tuple_to_list)
                elif datatype is dict and 'to_dict' not in value:
                    self.convert_object_to_dict(old_dict = value)
                elif datatype in (int, float, bool, str, bytearray, type(None)):
                    pass
                elif datatype is FunctionType:
                    lambda_str = self.__get_str_from_lambda(value)
                    old_dict[key] = lambda_str
                    # debug(lambda_str)
                elif datatype is np.ndarray:
                    if value.size >= 1024:
                        content_byte = value.tobytes()
                        length = len(content_byte)
                        self.shmem.write(contents=content_byte)
                        ndarray = NPArray(value.shape, length, value.dtype.str)
                        old_dict[key] = ndarray.__dict__
                    else:
                        old_dict[key] = value.tolist()
                    pass
                elif datatype is bytes:
                    # old_dict[key] = value.decode()
                    # debug(type(old_dict[key]))
                    old_dict[key] = len(value)
                    self.shmem.write(contents=value)
                else:
                    old_dict[key] = value.__dict__
                    # debug(f'[warning] unknown type {type(value)} is converted to dict.')
                    # raise Exception(f'No such type! Error! {type(value)}')

        if old_list is not None:
            for index, elem in enumerate(old_list):
                datatype = type(elem)
                if isinstance(elem, TFDataType.Tensor):
                    old_list[index] = elem.to_dict()
                elif datatype is TFDtypes:
                    old_list[index] = elem.value
                elif datatype is list:
                    self.convert_object_to_dict(old_list = elem)
                elif datatype is tuple:
                    old_list[index] = tuple_to_list = list(elem)
                    self.convert_object_to_dict(old_list = tuple_to_list)
                elif datatype is dict and 'to_dict' not in elem:
                    self.convert_object_to_dict(old_dict = elem)
                elif datatype in (int, float, bool, str,bytearray, type(None)):
                    pass
                elif datatype is FunctionType:
                    lambda_str = self.__get_str_from_lambda(elem)
                    old_list[index] = lambda_str
                    # debug(lambda_str)
                elif datatype is np.ndarray:
                    if elem.size >= 1024:
                        content_byte = elem.tobytes()
                        length = len(content_byte)
                        self.shmem.write(contents=content_byte)
                        ndarray = NPArray(elem.shape, length, elem.dtype.str)
                        old_list[index] = ndarray.__dict__
                    else:
                        old_list[index] = elem.tolist()
                    pass
                elif datatype is bytes:
                    old_list[index] = len(elem)
                    self.shmem.write(contents=elem)
                else:
                    old_list[index] = elem.__dict__
                    # debug(f'[warning] unknown type {type(elem)} is converted to dict.')
                    # raise Exception(f'No such type! Error! {type(elem)}')
