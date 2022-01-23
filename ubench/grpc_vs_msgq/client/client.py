import sys, os
sys.path.append('proto')
import logging
import time
import argparse
import subprocess

import grpc
import exp_pb2, exp_pb2_grpc
from concurrent import futures
import  json
from sysv_ipc import MessageQueue, IPC_CREX, SharedMemory, Semaphore
from enum import IntEnum


# class SharedMemoryChannel:
#     def __init__(self, key, size):
#         self.key = key
#         print(f'key={key}, type={type(key)}')
#         self.shmem = SharedMemory(key, IPC_CREX, size=size)
#         self.sem = Semaphore(key, IPC_CREX, initial_value = 1)

#     def write(self, data):
#         self.sem.acquire()
#         self.shmem.write(data)
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

#     def finalize(self):
#         self.sem.remove()
#         self.shmem.detach()
#         self.shmem.remove()
POCKET_CLIENT=True
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


class PocketControl(IntEnum):
    CONNECT = 0x1
    DISCONNECT = 0x2
    HELLO = 0x3
    NOP = 0x4

CLIENT_TO_SERVER = 0x1
SERVER_TO_CLIENT = 0x2

class PocketMessageChannel:
    universal_key = 0x1001
    client_id = Utils.get_container_id()
    local_key = int(client_id[:8], 16)
    __instance = None


    @staticmethod
    def get_instance():
        if PocketMessageChannel.__instance == None:
            PocketMessageChannel()
        
        return PocketMessageChannel.__instance

    def __init__(self):
        # attach to global queue
        if PocketMessageChannel.__instance != None:
            raise Exception("Only one channel can be exist.")

        else:
            self.gq = MessageQueue(PocketMessageChannel.universal_key)
            self.shmem = SharedMemoryChannel(key=PocketMessageChannel.client_id, size=1 * (32 + 4 * 1024 * 1024))
            self.conn(PocketMessageChannel.local_key)
            PocketMessageChannel.__instance = self

    def conn(self, key):
            # create local queue
        self.lq = MessageQueue(key, IPC_CREX)

        msg_type = int(PocketControl.CONNECT)
        reply_type = msg_type | 0x40000000
        args_dict = {'client_id': PocketMessageChannel.client_id, 'key': key}
        args_dict['raw_type'] = msg_type
        
        args_json = json.dumps(args_dict)

        self.gq.send(args_json, type = CLIENT_TO_SERVER)
        raw_msg, _ = self.lq.receive(block=True, type=reply_type)
        msg = json.loads(raw_msg)
        # debug(json.dumps(msg, indent=2, sort_keys=True))

    # control functions
    # for debugging
    def NOP(self):
        msg_type = int(PocketControl.NOP)
        reply_type = msg_type | 0x40000000
        args_dict = {'raw_type': msg_type}
        args_json = json.dumps(args_dict)

        # start = time.time()
        self.gq.send(args_json, block=True, type=CLIENT_TO_SERVER)
        raw_msg, _ = self.gq.receive(block=True, type=reply_type)
        # end = time.time()
        # logging.info(f'ipc_pure_rtt={end-start}')
        
        msg = json.loads(raw_msg)
        return msg['result']

class Experiments():
    shmem = SharedMemoryChannel(1234, 4*1024*1024)
    print(f'shmem created')

    @staticmethod
    def Init(stub, key):
        request = exp_pb2.InitRequest()
        response: exp_pb2.InitResponse

        request.key = key
        response = stub.Init(request)

    @staticmethod
    def Echo(stub, data):
        request = exp_pb2.EchoRequest()
        response: exp_pb2.EchoResponse
        
        request.data = data
        response = stub.Echo(request)

        return response.data

    @staticmethod
    def SendFilePath(stub, container_id, path):
        request = exp_pb2.SendFilePathRequest()
        response: exp_pb2.SendFilePathResponse
        
        request.container_id = container_id
        request.path = path

        start = time.time()
        response = stub.SendFilePath(request)
        end = time.time()
        logging.info(f'rtt(transmit_id)={end-start}')

        return response

    @staticmethod
    def SendFileBinary(stub, bin):
        request = exp_pb2.SendFileBinaryRequest()
        response: exp_pb2.SendFileBinaryResponse
        
        request.bin = bin
        start = time.time()
        response = stub.SendFileBinary(request)
        end = time.time()
        logging.info(f'rtt(transmit_bin)={end-start}')

        return response


    @staticmethod
    def ServerIOLatency(stub, container_id, path):
        request = exp_pb2.ServerIOLatencyRequest()
        response: exp_pb2.ServerIOLatencyResponse
        
        request.container_id = container_id
        request.path = path

        response = stub.ServerIOLatency(request)
        logging.info(f'latency(file_io_server)={response.log}')

        return response

    @staticmethod
    def SendViaShmem(stub, uri):
        request = exp_pb2.SendViaShmemRequest()
        response: exp_pb2.SendViaShmemResponse
        
        start = time.time()
        data = open(uri, 'rb').read()
        Experiments.shmem.write(contents=data)
        request.data_size = len(data)
        
        response = stub.SendViaShmem(request)
        end = time.time()
        logging.info(f'rtt(transmit_shmem)={end-start}')

        return response

    @staticmethod
    def SendViaShmem_ExcludeIO(stub, uri):
        request = exp_pb2.SendViaShmem_ExcludeIORequest()
        response: exp_pb2.SendViaShmem_ExcludeIOResponse
        
        start = time.time()
        data = open(uri, 'rb').read()
        Experiments.shmem.write(contents=data)

        request.data_size = len(data)

        response = stub.SendViaShmem(request)
        end = time.time()
        logging.info(f'rtt(transmit_shmem_no_io)={end-start}')

        return response

    @staticmethod
    def gRPCNOP(stub):
        request = exp_pb2.NOPRequest()
        response: exp_pb2.NOPResponse
        

        start = time.time()
        response = stub.NOP(request)
        end = time.time()
        logging.info(f'rtt(grpc_nop)={end-start}')

        return response

    @staticmethod
    def lIPCNOP(msgq):
        request = exp_pb2.SendViaShmem_ExcludeIORequest()
        response: exp_pb2.SendViaShmem_ExcludeIOResponse
        
        start = time.time()
        response = msgq.NOP()
        end = time.time()
        logging.info(f'rtt(lipc_nop)={end-start}')

        return response

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', '-f', help='file path', type=str, required=True)
    args = parser.parse_args()
    file = os.path.abspath(args.file)

    server_addr = os.environ.get('SERVER_ADDR')
    # server_addr = 'localhost'
    container_id = subprocess.check_output('cat /proc/self/cgroup | grep cpuset | cut -d/ -f3 | head -1', shell=True, encoding='utf-8').strip()


    logging.info(server_addr)
    channel = grpc.insecure_channel(f'{server_addr}:1991', \
        options=(('grpc.max_send_message_length', 100 * 1024 * 1024), \
        ('grpc.max_receive_message_length', 100 * 1024 * 1024), \
        ('grpc.max_message_length', 100 * 1024 * 1024),
        ('grpc.enable_http_proxy', 0)) \
    )
    stub = exp_pb2_grpc.ExperimentServiceStub(channel)

    Experiments.Init(stub, 1234)

    returned_data = Experiments.Echo(stub, 'Hello Misun!')
    logging.info(f'returned_data={returned_data}')

    Experiments.SendFilePath(stub, container_id, file) # path

    start = time.time()
    read_image = open(file, 'rb').read()
    end = time.time()
    logging.info(f'latency(file_io_client)={end-start}')

    Experiments.SendFileBinary(stub, read_image) # rpc

    Experiments.ServerIOLatency(stub, container_id, file) # server io

    Experiments.SendViaShmem(stub, file)

    Experiments.SendViaShmem_ExcludeIO(stub, file)

    Experiments.gRPCNOP(stub)

    msgq = PocketMessageChannel.get_instance()
    Experiments.lIPCNOP(msgq)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, \
                        format='[%(asctime)s|CLIENT] %(message)s')
    main()