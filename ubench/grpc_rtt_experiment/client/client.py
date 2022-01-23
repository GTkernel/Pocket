import sys, os
sys.path.append('proto')
import logging
import time
import argparse
import subprocess

import grpc
import exp_pb2, exp_pb2_grpc
from concurrent import futures
import sysv_ipc

class SharedMemoryChannel:
    def __init__(self, key, size):
        self.key = key
        self.shmem = sysv_ipc.SharedMemory(key, sysv_ipc.IPC_CREX, size=size)
        self.sem = sysv_ipc.Semaphore(key, sysv_ipc.IPC_CREX, initial_value = 1)

    def write(self, data):
        self.sem.acquire()
        self.shmem.write(data)
        self.sem.release()

    def read(self, size):
        self.sem.acquire()
        data = self.shmem.read(size)
        self.sem.release()
        return data

    def view(self, size):
        self.sem.acquire()
        mv = memoryview(self.shmem)
        self.sem.release()
        return mv[:size]

    def finalize(self):
        self.sem.remove()
        self.shmem.detach()
        self.shmem.remove()

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
        
        data = open(uri, 'rb').read()
        Experiments.shmem.write(data)
        request.data_size = len(data)
        
        start = time.time()
        response = stub.SendViaShmem(request)
        end = time.time()
        logging.info(f'rtt(transmit_shmem)={end-start}')

        return response

    @staticmethod
    def SendViaShmem_ExcludeIO(stub, uri):
        request = exp_pb2.SendViaShmem_ExcludeIORequest()
        response: exp_pb2.SendViaShmem_ExcludeIOResponse
        
        data = open(uri, 'rb').read()
        Experiments.shmem.write(data)

        request.data_size = len(data)
        start = time.time()

        response = stub.SendViaShmem(request)
        end = time.time()
        logging.info(f'rtt(transmit_shmem_no_io)={end-start}')

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


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, \
                        format='[%(asctime)s|CLIENT] %(message)s')
    main()