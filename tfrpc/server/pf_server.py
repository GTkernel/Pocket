#!/usr/bin/python
import os
import subprocess, time

from concurrent import futures
import logging
import grpc
import signal

from absl import flags
from absl.flags import FLAGS

import tensorflow as tf
import numpy as np

import sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from models import YoloV3

from batch_norm import BatchNormalization
from utils import broadcast_iou
import threading
from enum import Enum
from sysv_ipc import Semaphore, SharedMemory, MessageQueue, IPC_CREX



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

from pocketmgr_pf import PocketManager
if __name__ == '__main__':
    FLAGS(sys.argv)
    signal.signal(signal.SIGINT, finalize)

    import subprocess, psutil
    cpu_sockets =  int(subprocess.check_output('cat /proc/cpuinfo | grep "physical id" | sort -u | wc -l', shell=True))
    phy_cores = int(psutil.cpu_count(logical=False)/cpu_sockets)
    print(cpu_sockets, phy_cores)

    tf.config.threading.set_inter_op_parallelism_threads(cpu_sockets) # num of sockets: 2
    tf.config.threading.set_intra_op_parallelism_threads(phy_cores) # num of phy cores: 12
    os.environ['OMP_NUM_THREADS'] = str(phy_cores)
    os.environ['KMP_AFFINITY'] = 'granularity=fine,verbose,compact,1,0'

    mgr = PocketManager()
    mgr.start()
    exit()

    msgq = MessageQueue(universal_key, IPC_CREX)
    data, type = msgq.receive()
    print(data)
    if type == 0x1:
        reply_type = type | 0x40000000
        print(reply_type)
        msgq.send(data, type = reply_type)

    exit()
    logging.basicConfig()
    FLAGS(sys.argv)
    # print(f'hostroot={hostroot}')
    subprocess.check_call(f'mkdir -p {hostroot}', shell=True)
    time.sleep(3)
    serve()