from time import time
import os, sys
import tensorflow as tf
import numpy as np
import logging
import argparse
from time import time

import tensorflow as tf
import os
import shutil

import tensorflow_text as text # text should be imported!
import sysv_ipc

MODEL = None
IMDB_DATASET = '/dataset/imdb/'
# https://www.tensorflow.org/text/tutorials/classify_text_with_bert
# talking-heads_base
# tfhub_handle_encoder = 'https://tfhub.dev/tensorflow/talkheads_ggelu_bert_en_base/1'
# tfhub_handle_preprocess = 'https://tfhub.dev/tensorflow/bert_en_uncased_preprocess/3'

def configs():
    logging.basicConfig(level=logging.DEBUG, \
                        format='[%(asctime)s, %(lineno)d %(funcName)s | TalkingHeads] %(message)s')
    parser = argparse.ArgumentParser()
    parsed_args = parser.parse_args()

    import subprocess, psutil
    cpu_sockets =  int(subprocess.check_output('cat /proc/cpuinfo | grep "physical id" | sort -u | wc -l', shell=True))
    phy_cores = int(psutil.cpu_count(logical=False)/cpu_sockets)
    # print(cpu_sockets, phy_cores)

    tf.config.threading.set_inter_op_parallelism_threads(cpu_sockets) # num of sockets: 2
    tf.config.threading.set_intra_op_parallelism_threads(phy_cores) # num of phy cores: 12
    os.environ['OMP_NUM_THREADS'] = str(phy_cores)
    os.environ['KMP_AFFINITY'] = 'granularity=fine,verbose,compact,1,0'

def print_my_examples(inputs, results):
    result_for_printing = [f'input: {inputs[i]:<30} : score: {results[i][0]:.6f}'
                                for i in range(len(inputs))]
    print(*result_for_printing, sep='\n')
    print()

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
    stat_dict = measure_resource_usage()
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

if __name__ == '__main__':
    configs()

    dataset_name = 'imdb-bert_expert'
    saved_model_path = '/models/imdb_prediction/{}_bert'.format(dataset_name.replace('/', '_'))

    # classifier_model.save(saved_model_path, include_optimizer=False)
    s = time()
    reloaded_model = tf.saved_model.load(saved_model_path)
    boot = e = time()
    
    mq_key = 20210131
    mq = sysv_ipc.MessageQueue(mq_key)
    container_name = os.environ.get('CONTAINER_NAME')
    mq.send(f'{container_name} default')
    try:
        data, _ = mq.receive()
    except:
        pass
    boot = time()

    examples = [
        'this is such an amazing movie!',  # this is the same sentence tried earlier
        'The movie was great!',
        'The movie was meh.',
        'The movie was okish.',
        'The movie was terrible...'
    ]

    t1 = time()
    reloaded_results = tf.sigmoid(reloaded_model(tf.constant(examples)))
    t2 = time()
    # print(t2-t1)
    # print_my_examples(examples, reloaded_results)

    t1 = time()
    reloaded_results = tf.sigmoid(reloaded_model(tf.constant(examples)))
    t2 = time()
    # print(t2-t1)
    # original_results = tf.sigmoid(classifier_model(tf.constant(examples)))
    # print_my_examples(examples, reloaded_results)

    t1 = time()
    reloaded_results = tf.sigmoid(reloaded_model(tf.constant(['it is an awesome movie!'])))
    t2 = time()
    # print(t2-t1)

    # https://www.rogerebert.com/reviews/great-movie-psycho-1960
    with open('psycho.txt') as f:
        roger_ebert_hitchcock_psycho = f.readlines()
    s = time()
    reloaded_results = tf.sigmoid(reloaded_model(tf.constant(roger_ebert_hitchcock_psycho)))
    e = time()
    # print(t2-t1)
    logging.info(f'inference_time={e-s}')
    # print_my_examples(roger_ebert_hitchcock_psycho, reloaded_results)
    # original_results = tf.sigmoid(classifier_model(tf.constant(examples)))

    # print('Results from the saved model:')
    
    index = os.environ.get('CONTAINER_ID')
    boot = round(boot * 1000000)
    print(f'[parse/boot/talkingheads/cr/{index}/ready] {boot}')
    finalize()
