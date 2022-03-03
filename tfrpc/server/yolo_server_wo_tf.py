#!/usr/bin/python
import os
import subprocess, time
import socket
# from multiprocessing import Process # todo: remove?

# todo: remove these after debugging
# os.environ['YOLO_SERVER'] = '1'
# from multiprocessing import Process, Pipe, Manager
# import time
# import contexttimer
# def child_process(func):
#     """Makes the function run as a separate process."""
#     def wrapper(*args, **kwargs):
#         def worker(conn, func, args, kwargs):
#             conn.send(func(*args, **kwargs))
#             conn.close()
#         parent_conn, child_conn = Pipe()
#         p = Process(target=worker, args=(child_conn, func, args, kwargs))
#         p.start()
#         ret = parent_conn.recv()
#         p.join()
#         return ret
#     return wrapper

from concurrent import futures
import logging
import signal

from absl import flags
from absl.flags import FLAGS

import sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# sys.path.insert(0, os.path.abspath('../../yolov3_tf2'))
# os.chdir('../../yolov3-tf2')
# sys.path.insert(0, os.path.abspath('yolov3_tf2'))
# print(os.getcwd()) ##
from batch_norm import BatchNormalization
from utils import broadcast_iou
import threading
from enum import Enum
from sysv_ipc import Semaphore, SharedMemory, MessageQueue, IPC_CREX

def finalize(signum, frame):
    # if 'cProfile' in dir():
    #     cProfile.create_stats()
    sys.exit(0)

from pocketmgr import PocketManager
if __name__ == '__main__':
    FLAGS(sys.argv)
    signal.signal(signal.SIGINT, finalize)

    import subprocess, psutil
    cpu_sockets =  int(subprocess.check_output('cat /proc/cpuinfo | grep "physical id" | sort -u | wc -l', shell=True))
    phy_cores = int(psutil.cpu_count(logical=False)/cpu_sockets)
    print(cpu_sockets, phy_cores)

    mgr = PocketManager()
    mgr.start()
    exit()