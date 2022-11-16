from time import time
# https://gist.github.com/yrevar/942d3a0ac09ec9e5eb3a
# imagenet index label
import os, sys
import tensorflow as tf
import numpy as np
import logging
import argparse
sys.path.insert(0, '/root/')
CUR_DIR = os.path.dirname(os.path.realpath(__file__))
COCO_DIR = '/root/coco2017'
# IMG_FILE = '000000581206.jpg' # Hot dogs
# IMG_FILE = '000000578967.jpg' # Train
# IMG_FILE = '000000093965.jpg' # zebra
# IMG_FILE = '000000104424.jpg' # a woman with a tennis racket
IMG_FILE = '000000292446.jpg' # pizza
CLASS_LABLES_FILE = 'imagenet1000_clsidx_to_labels.txt'
CLASSES = {}
MODEL: tf.keras.applications.MobileNetV2

def configs():
    global IMG_FILE
    logging.basicConfig(level=logging.DEBUG, \
                        format='[%(asctime)s, %(lineno)d %(funcName)s | MobileNetV2] %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', default=IMG_FILE)
    parsed_args = parser.parse_args()
    IMG_FILE = parsed_args.image

    import subprocess, psutil
    cpu_sockets =  int(subprocess.check_output('cat /proc/cpuinfo | grep "physical id" | sort -u | wc -l', shell=True))
    phy_cores = int(psutil.cpu_count(logical=False)/cpu_sockets)
    print(cpu_sockets, phy_cores)

    tf.config.threading.set_inter_op_parallelism_threads(cpu_sockets) # num of sockets: 2
    tf.config.threading.set_intra_op_parallelism_threads(phy_cores) # num of phy cores: 12
    os.environ['OMP_NUM_THREADS'] = str(phy_cores)
    os.environ['KMP_AFFINITY'] = 'granularity=fine,verbose,compact,1,0'

def load_classes():
    with open(CLASS_LABLES_FILE) as file:
        raw_labels = file.read().replace('{', '').replace('}', '').split('\n')
        for line in raw_labels:
            key, value = line.split(':')
            value = value.replace('\'', '').strip()
            if value[-1] is ',':
                value = value[:-1]

            CLASSES[int(key)] = value

def build_model():
    global MODEL

    MODEL = tf.keras.applications.MobileNetV2(input_shape = (224, 224, 3),
                                              include_top = True,
                                              weights = 'imagenet')

def resize_image(file):
    path = os.path.join(COCO_DIR, file)
    image = tf.image.decode_image(open(path, 'rb').read()) / 255
    image = tf.image.resize(image, (224, 224))
    image = tf.reshape(image, (1, image.shape[0], image.shape[1], image.shape[2]))
    return image

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

def finalize():
    # if 'cProfile' in dir():
    #     cProfile.create_stats()
    # stat_dict = measure_resource_usage()
    # print('[resource_usage]', f'cputime.total={stat_dict.get("cputime.total", None)}')
    # print('[resource_usage]', f'cputime.user={stat_dict.get("cputime.user", None)}')
    # print('[resource_usage]', f'cputime.sys={stat_dict.get("cputime.sys", None)}')
    # print('[resource_usage]', f'memory.max_usage={stat_dict.get("memory.max_usage", None)}')
    # print('[resource_usage]', f'memory.memsw.max_usage={stat_dict.get("memory.memsw.max_usage", None)}')
    # print('[resource_usage]', f'memory.stat.pgfault={stat_dict.get("memory.stat.pgfault", None)}')
    # print('[resource_usage]', f'memory.stat.pgmajfault={stat_dict.get("memory.stat.pgmajfault", None)}')
    # print('[resource_usage]', f'memory.failcnt={stat_dict.get("memory.failcnt", None)}')
    sys.stdout.flush()
    os._exit(0)

if __name__ == '__main__':
    configs()
    load_classes()
    s = time()
    build_model()
    e = time()
    logging.info(f'graph_construction_time={e-s}')
    image = resize_image(IMG_FILE)
    s = time()
    for i in range(10):
        result = MODEL(image)
    e = time()
    logging.info(f'inference_time={e-s}')
    cls = np.argmax(result)
    logging.info(f'{CLASSES[cls]}')

    finalize()
