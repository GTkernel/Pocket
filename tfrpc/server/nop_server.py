#!/usr/bin/python
import os
import subprocess
import signal

from absl import flags
from absl.flags import FLAGS

import tensorflow as tf
import numpy as np

import sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def finalize(signum, frame):
    # if 'cProfile' in dir():
    #     cProfile.create_stats()
    sys.exit(0)

from pocketmgr_nop import PocketManager
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
