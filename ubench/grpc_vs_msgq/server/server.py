import sys
sys.path.append('proto')
import logging
import subprocess

import grpc
import exp_pb2, exp_pb2_grpc
from concurrent import futures
import time

import json
from sysv_ipc import MessageQueue, IPC_CREX, SharedMemory, Semaphore
from threading import Thread
from enum import IntEnum
from time import sleep

# class SharedMemoryChannel:
#     def __init__(self, key):
#         self.key = key
#         self.shmem = SharedMemory(key)
#         self.sem = Semaphore(key)

#     def write(self, uri):
#         self.sem.acquire()
#         self.shmem.write(open(uri, 'rb').read())
#         self.sem.release()

#     def read(self, size):
#         self.sem.acquire()
#         data = self.shmem.read(size)
#         self.sem.release()
#         return data

#     def view(self, size):
#         self.sem.acquire()
#         mv = memoryview(self.shmem)
#         self.sem.release()
#         return mv[:size]
POCKET_CLIENT=False
class SharedMemoryChannel:
    # [0: 32) Bytes: header
    ### [0, 4) Bytes: size
    # [32, -] Bytes: data
    def __init__(self, key, size=None, path=None):
        if type(key) != type(1):
            self.key = int(key[:8], 16)
        else:
            self.key = key
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

def debug_ls(dir: str):
    output = subprocess.check_output(f'ls -al {dir}', shell=True, encoding='utf-8').strip()
    logging.debug(output)

CLIENT_TO_SERVER = 0x1
SERVER_TO_CLIENT = 0x2

class PocketControl(IntEnum):
    CONNECT = 0x1
    DISCONNECT = 0x2
    HELLO = 0x3
    NOP = 0x4

class ReturnValue(IntEnum):
    OK = 0
    ERROR = 1
    EXCEPTIONRAISED = 2

def debug(*args):
    import inspect
    filename = inspect.stack()[1].filename
    lineno = inspect.stack()[1].lineno
    caller = inspect.stack()[1].function
    print(f'debug>> [{filename}:{lineno}, {caller}]', *args)

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
        # temporarily off for verifying nop
        # self.handle_clients_thread = Thread(target=self.pocket_serving_client)
        self.queues_dict = {}
        self.per_client_object_store = {}
        self.model_dict = {}
        self.shmem_dict = {}
        PocketManager.__instance = self

    def start(self):
        debug('start!')
        self.gq_thread.start()
        # self.handle_clients_thread.start()

        # self.handle_clients_thread.join()
        self.gq_thread.join()

    def pocket_new_connection(self):
        while True:
            # debug('pocket_new_connection')
            raw_msg, raw_type = self.gq.receive(block=True, type=CLIENT_TO_SERVER)
            args_dict = json.loads(raw_msg)
            raw_type = args_dict['raw_type']
        
            # debug('received')
            # debug(hex(raw_type))

            type = PocketControl(raw_type)
            reply_type = raw_type | 0x40000000
            if type == PocketControl.CONNECT:
                self.add_client_queue(args_dict['client_id'], args_dict['key'])
                self.per_client_object_store[args_dict['client_id']] = {}
                self.send_ack_to_client(args_dict['client_id'])
                self.shmem_dict[args_dict['client_id']] = SharedMemoryChannel(args_dict['client_id'])
            elif type == PocketControl.DISCONNECT:
                # Todo: Clean up
                pass
                self.per_client_object_store.pop(args_dict['client_id'], None)
            elif type == PocketControl.HELLO:
                return_dict = {'result': ReturnValue.OK.value, 'message': args_dict['message']}
                return_byte_obj = json.dumps(return_dict)
                self.gq.send(return_byte_obj, type=reply_type)
            elif type == PocketControl.NOP:
                return_dict = {'result': ReturnValue.OK.value}
                return_byte_obj = json.dumps(return_dict)
                self.gq.send(return_byte_obj, type=reply_type)
                
            sleep(0.0001) ##### EXPRIMENTAL_PARAMETER: This need to be zero to get optimal results.

    def add_client_queue(self, client_id, key):
        client_queue = MessageQueue(key)
        self.queues_dict[client_id] = client_queue

    def send_ack_to_client(self, client_id):
        return_dict = {'result': ReturnValue.OK.value, 'message': 'you\'re acked!'}
        return_byte_obj = json.dumps(return_dict)
        reply_type = PocketControl.CONNECT.value | 0x40000000

        self.queues_dict[client_id].send(return_byte_obj, block=True, type=reply_type)

SHMEM = None
class ExperimentSet(exp_pb2_grpc.ExperimentServiceServicer):
    def Init(self, request, context):
        global SHMEM
        print(f'Init')
        response = exp_pb2.InitResponse()
        key = request.key

        SHMEM = SharedMemoryChannel(key)
        return response


    def Echo(self, request, context):
        print(f'Echo')
        response = exp_pb2.EchoResponse()
        
        response.data = request.data

        return response

    def SendFilePath(self, request, context):
        print(f'SendFilePath')
        response = exp_pb2.SendFilePathResponse()

        return response

    def SendFileBinary(self, request, context):
        print(f'SendFileBinary')
        response = exp_pb2.SendFileBinaryResponse()

        return response

    def ServerIOLatency(self, request, context):
        print(f'ServerIOLatency')
        response = exp_pb2.ServerIOLatencyResponse()
        
        path = request.path
        container_id = request.container_id
        prefix = '/layers/' + subprocess.check_output('docker inspect -f {{.GraphDriver.Data.MergedDir}} ' + container_id, shell=True).decode('utf-8').strip().strip('/').split('/')[4] + '/merged'
        
        # debug_ls('/')
        # debug_ls('/layers')
        # debug_ls(prefix)
        if path.startswith('/tmpfs/'):
            full_path = path
        else:
            full_path = prefix + path
        start = time.time()
        read_img = open(full_path, 'rb').read()
        end = time.time()
        response.log = str(end-start)

        return response

    def SendViaShmem(self, request, context):
        print(f'SendViaShmem')
        response = exp_pb2.SendViaShmemResponse()

        data = SHMEM.read(request.data_size)
        return response

    def SendViaShmem_ExcludeIO(self, request, context):
        print(f'SendViaShmem_ExcludeIO')
        response = exp_pb2.SendViaShmem_ExcludeIOResponse()
        return response

    def NOP(self, request, context):
        print(f'NOP')
        response = exp_pb2.NOPResponse()
        return response

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=47),
                         options=[('grpc.so_reuseport', 1),
                                  ('grpc.max_send_message_length', -1),
                                  ('grpc.max_receive_message_length', -1)])
    exp_pb2_grpc.add_ExperimentServiceServicer_to_server(ExperimentSet(), server)
    server.add_insecure_port('[::]:1991')
    server.start()
    logging.info('Server started!')
    server.wait_for_termination()

def serve_lipc():
    mgr = PocketManager()
    mgr.start()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, \
                        format='[%(asctime)s|SERVER] %(message)s')
    s1 = Thread(target=serve)
    # s2 = Thread(target=serve_lipc)
    s1.start()
    # s2.start()
    # s1.join()
    # s2.join()

    # serve()
    serve_lipc()