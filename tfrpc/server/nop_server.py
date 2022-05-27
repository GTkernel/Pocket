#!/usr/bin/python
import os
import subprocess
import signal

from absl import flags
from absl.flags import FLAGS

TF_SERVER = 'on' if os.environ.get('TF_SERVER', '0') == '1' else 'off'
if TF_SERVER == 'on':
    import tensorflow as tf
    import numpy as np

import sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
# print(TF_SERVER)
# print('tfserver', os.environ.get('TF_SERVER'))
# sys.stdout.flush()

def finalize(signum, frame):
    # if 'cProfile' in dir():
    #     cProfile.create_stats()
    stat_dict = Utils.measure_resource_usage()
    print('[resource_usage]', f'cputime.total={stat_dict.get("cputime.total", None)}')
    print('[resource_usage]', f'cputime.user={stat_dict.get("cputime.user", None)}')
    print('[resource_usage]', f'cputime.sys={stat_dict.get("cputime.sys", None)}')
    print('[resource_usage]', f'memory.max_usage={stat_dict.get("memory.max_usage", None)}')
    print('[resource_usage]', f'memory.memsw.max_usage={stat_dict.get("memory.memsw.max_usage", None)}')
    print('[resource_usage]', f'memory.stat.pgfault={stat_dict.get("memory.stat.pgfault", None)}')
    print('[resource_usage]', f'memory.stat.pgmajfault={stat_dict.get("memory.stat.pgmajfault", None)}')
    print('[resource_usage]', f'memory.failcnt={stat_dict.get("memory.failcnt", None)}')
    sys.stdout.flush()
    os._exit(0)

from pocketmgr_nop import PocketManager, Utils
if __name__ == '__main__':
    FLAGS(sys.argv)
    signal.signal(signal.SIGTERM, finalize)

    import subprocess, psutil
    cpu_sockets =  int(subprocess.check_output('cat /proc/cpuinfo | grep "physical id" | sort -u | wc -l', shell=True))
    phy_cores = int(psutil.cpu_count(logical=False)/cpu_sockets)
    print(cpu_sockets, phy_cores)

    if TF_SERVER == 'on':
        physical_devices = tf.config.experimental.list_physical_devices('GPU')
        if len(physical_devices) > 0:
            tf.config.experimental.set_memory_growth(physical_devices[0], True)
        tf.config.threading.set_inter_op_parallelism_threads(cpu_sockets) # num of sockets: 2
        tf.config.threading.set_intra_op_parallelism_threads(phy_cores) # num of phy cores: 12
        os.environ['OMP_NUM_THREADS'] = str(phy_cores)
        os.environ['KMP_AFFINITY'] = 'granularity=fine,verbose,compact,1,0'

    mgr = PocketManager()
    mgr.start()
