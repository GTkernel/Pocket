import sys
sys.path.append('proto')
import logging
import subprocess

import grpc
import exp_pb2, exp_pb2_grpc
from concurrent import futures
import time
import sysv_ipc

class SharedMemoryChannel:
    def __init__(self, key):
        self.key = key
        self.shmem = sysv_ipc.SharedMemory(key)
        self.sem = sysv_ipc.Semaphore(key)

    def write(self, uri):
        self.sem.acquire()
        self.shmem.write(open(uri, 'rb').read())
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

def debug_ls(dir: str):
    output = subprocess.check_output(f'ls -al {dir}', shell=True, encoding='utf-8').strip()
    logging.debug(output)

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

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, \
                        format='[%(asctime)s|SERVER] %(message)s')
    serve()