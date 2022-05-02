import os
import sys
import argparse
import logging

DIRECTORY = ''

def arg_init():
    global DIRECTORY

    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--dir', type=str)

    parsed_args = parser.parse_args()
    DIRECTORY = os.path.abspath(parsed_args.dir)

def is_monolithic(file):
    return 'monolithic' in file

def get_index(file):
    if file.endswith('.log'):
        file = file[:-4]
    if file.endswith('.tottime'):
        file = file[:-8]
    if os.path.basename(file).replace('.', '-').split('-')[-2] == 'server':
        return os.path.basename(file).replace('.', '-').split('-')[3]
        file = file[:-8]
    if os.path.basename(file).replace('.', '-').split('-')[-2] == 'client':
        return os.path.basename(file).replace('.', '-').split('-')[3]
        file = file[:-8]
    if os.path.basename(file).replace('.', '-').split('-')[-2] == 'monolithic':
        return os.path.basename(file).replace('.', '-').split('-')[-1]

    file = os.path.basename(file)
    elem_list = file.replace('.','-').split('-')
    index_str = elem_list[-2]
    logging.info(elem_list)
    index = int(index_str)
    return index

def get_latency(file):
    value = ''
    with open(file, 'r') as f:
        value = f.read()
    return value

def get_graph(file):
    elem_list = []
    with open(file, 'r') as f:
        elem_list = f.read().split()

    graph_time = elem_list[5]
    return graph_time

def get_inf(file):
    elem_list = []
    with open(file, 'r') as f:
        elem_list = f.read().split()

    inf_time = elem_list[5]
    return inf_time

def get_tot_time(line):
    return float(line.split()[1])

def is_server(file):
    return 'server' in os.path.basename(file)

def get_rusage(file):
    logging.info(file)
    content = []
    content_map = {}
    with open(file, 'r') as f:
        content = f.readlines()

    for line in content:
        elem_list = line.strip().split('=')
        if elem_list[0] == 'page_fault':
            elem_list[0] = 'pagefault'
        if elem_list[0] == 'page_fault_init':
            elem_list[0] = 'pagefault_init'

        content_map[elem_list[0]] = elem_list[1]

    cpu_usage = content_map['cpu_usage']
    mem_usage = content_map['max_memory_usage']

    if is_server(file):
        pagefault = str(int(content_map['pagefault']) - int(content_map['pagefault_init']))
    else:
        pagefault = content_map['pagefault']

    return cpu_usage, mem_usage, pagefault
    

def get_perf_counters(file):
    logging.info(file)
    content = []
    content_map = {}
    with open(file, 'r') as f:
        content = f.readlines()

    new_content = []
    for line in content:
        line = line.strip().split()
        if len(line) > 0:
            new_content.append(line)

    content = new_content[2:]
    logging.info(content)

    for line in content:
        content_map[line[1]] = line[0]

    cpu_cycle = content_map['cpu-cycles']
    cache_miss = content_map['cache-misses']
    itlb_miss = content_map['iTLB-load-misses']
    dtlb_miss = content_map['dTLB-load-misses']

    return cpu_cycle, cache_miss, itlb_miss, dtlb_miss

def get_exec_composition(file):
    logging.info(file)
    content = []
    content_map = {}
    with open(file, 'r') as f:
        content = f.readlines()

    total_time = content[2].strip().split()[7]
    server_exec=0
    ipc=0
    daemoncomm=0
    serialize =0

    for line in content:
        line = line.strip()
        if 'receive' in line and 'sysv_ipc.MessageQueue' in line:
            logging.info(f'line={line}, {get_tot_time(line)}')
            server_exec = get_tot_time(line)
        elif 'send' in line and 'sysv_ipc.MessageQueue' in line:
            logging.info(f'line={line}, {get_tot_time(line)}')
            ipc = get_tot_time(line)
        elif 'recv' in line and '_socket.socket' in line:
            logging.info(f'line={line}, {get_tot_time(line)}')
            daemoncomm += get_tot_time(line)
            ipc = get_tot_time(line)
        elif 'send' in line and '_socket.socket' in line:
            logging.info(f'line={line}, {get_tot_time(line)}')
            daemoncomm += get_tot_time(line)
        elif 'json' in line:
            logging.info(f'line={line}, {get_tot_time(line)}')
            serialize += get_tot_time(line)

    return str(total_time), str(server_exec), str(ipc), str(daemoncomm), str(serialize)
    



def aggregate_latency_data(directory, number):
    # pass
    os.makedirs(f'{directory}/../aggregate', exist_ok=True)
    # logging.info(f'directory={directory}')
    # logging.info(f'{os.listdir(directory)}')

    graph_file = f'{directory}/../aggregate/graph-{number}'
    inf_file = f'{directory}/../aggregate/inf-{number}'
    latency_file = f'{directory}/../aggregate/latency-{number}'

    graph_list_cold = []
    graph_list_warm = []

    inf_list_cold = []
    inf_list_warm = []

    latency_list_cold = []
    latency_list_warm = []

    with open(graph_file, 'w+') as f:
        f.seek(0)
        f.truncate()

    with open(inf_file, 'w+') as f:
        f.seek(0)
        f.truncate()

    with open(latency_file, 'w+') as f:
        f.seek(0)
        f.truncate()

    for folder in os.listdir(directory):
        folder = f'{directory}/{folder}'
        if os.path.isfile(folder):
            continue
        logging.info(f'folder={folder}')

        if folder.endswith('graph'):
            for file in os.listdir(folder):
                file = f'{folder}/{file}'
                index = get_index(file)
                data = get_graph(file)
                if index is 0:
                    graph_list_cold.append(data)
                else:
                    graph_list_warm.append(data)


    for folder in os.listdir(directory):
        folder = f'{directory}/{folder}'
        if os.path.isfile(folder):
            continue
        logging.info(f'folder={folder}')

        if folder.endswith('latency'):
            for file in os.listdir(folder):
                file = f'{folder}/{file}'
                index = get_index(file)
                data = get_latency(file)
                if index is 0:
                    latency_list_cold.append(data)
                else:
                    latency_list_warm.append(data)

    for folder in os.listdir(directory):
        folder = f'{directory}/{folder}'
        if os.path.isfile(folder):
            continue
        logging.info(f'folder={folder}')

        if folder.endswith('inf'):
            for file in os.listdir(folder):
                file = f'{folder}/{file}'
                index = get_index(file)
                data = get_inf(file)
                if index is 0:
                    inf_list_cold.append(data)
                else:
                    inf_list_warm.append(data)

    with open(graph_file, 'w') as f:
        for elem in graph_list_cold:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in graph_list_warm:
            f.write(f'{elem}\n')

    with open(inf_file, 'w') as f:
        for elem in inf_list_cold:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in inf_list_warm:
            f.write(f'{elem}\n')

    with open(latency_file, 'w') as f:
        for elem in latency_list_cold:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in latency_list_warm:
            f.write(f'{elem}\n')


def aggregate_rusage_data(directory, number):
    # pass
    os.makedirs(f'{directory}/../aggregate', exist_ok=True)
    # logging.info(f'directory={directory}')
    # logging.info(f'{os.listdir(directory)}')

    cpu_file = f'{directory}/../aggregate/cpu_usage-{number}'
    mem_file = f'{directory}/../aggregate/max_mem-{number}'
    pgf_file = f'{directory}/../aggregate/pgfault-{number}'

    cpu_list_cold = []
    cpu_list_warm = []
    cpu_list_server = []

    mem_list_cold = []
    mem_list_warm = []
    mem_list_server = []

    pgf_list_cold = []
    pgf_list_warm = []
    pgf_list_server = []

    with open(cpu_file, 'w+') as f:
        f.seek(0)
        f.truncate()

    with open(mem_file, 'w+') as f:
        f.seek(0)
        f.truncate()

    with open(pgf_file, 'w+') as f:
        f.seek(0)
        f.truncate()

    for folder in os.listdir(directory):
        folder = f'{directory}/{folder}'
        if os.path.isfile(folder):
            continue
        logging.info(f'folder={folder}')

        if folder.endswith('rusage'):
            for file in os.listdir(folder):
                file = f'{folder}/{file}'
                index = get_index(file)
                cpu_data, mem_data, pgf_data = get_rusage(file)

                if is_server(file):
                    cpu_list_server.append(cpu_data)
                    mem_list_server.append(mem_data)
                    pgf_list_server.append(pgf_data)
                elif index is 0:
                    cpu_list_cold.append(cpu_data)
                    mem_list_cold.append(mem_data)
                    pgf_list_cold.append(pgf_data)
                else:
                    cpu_list_warm.append(cpu_data)
                    mem_list_warm.append(mem_data)
                    pgf_list_warm.append(pgf_data)



    with open(cpu_file, 'w') as f:
        for elem in cpu_list_server:
            f.write(f'{elem}\n')

        f.write(f'\n')
        
        for elem in cpu_list_cold:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in cpu_list_warm:
            f.write(f'{elem}\n')

    with open(mem_file, 'w') as f:
        for elem in mem_list_server:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in mem_list_cold:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in mem_list_warm:
            f.write(f'{elem}\n')

    with open(pgf_file, 'w') as f:
        for elem in pgf_list_server:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in pgf_list_cold:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in pgf_list_warm:
            f.write(f'{elem}\n')

def aggregate_perf_data(directory, number):
    # pass
    os.makedirs(f'{directory}/../aggregate', exist_ok=True)
    # logging.info(f'directory={directory}')
    # logging.info(f'{os.listdir(directory)}')

    cpu_cycle_file = f'{directory}/../aggregate/cpu_cycle-{number}'
    cache_miss_file = f'{directory}/../aggregate/cache_miss-{number}'
    itlb_miss_file = f'{directory}/../aggregate/itlb_miss-{number}'
    dtlb_miss_file = f'{directory}/../aggregate/dtlb_miss-{number}'

    cpucycle_list_cold = []
    cpucycle_list_warm = []
    cpucycle_list_server = []

    cachemiss_list_cold = []
    cachemiss_list_warm = []
    cachemiss_list_server = []

    itlbmiss_list_cold = []
    itlbmiss_list_warm = []
    itlbmiss_list_server = []

    dtlbmiss_list_cold = []
    dtlbmiss_list_warm = []
    dtlbmiss_list_server = []

    with open(cpu_cycle_file, 'w+') as f:
        f.seek(0)
        f.truncate()

    with open(cache_miss_file, 'w+') as f:
        f.seek(0)
        f.truncate()

    with open(itlb_miss_file, 'w+') as f:
        f.seek(0)
        f.truncate()

    with open(dtlb_miss_file, 'w+') as f:
        f.seek(0)
        f.truncate()

    for folder in os.listdir(directory):
        folder = f'{directory}/{folder}'
        if os.path.isfile(folder):
            continue
        logging.info(f'folder={folder}')

        if folder.endswith('perf'):
            for file in os.listdir(folder):
                file = f'{folder}/{file}'
                index = get_index(file)
                cpu_cycle, cache_miss, itlbmiss, dtlbmiss = get_perf_counters(file)
                if is_server(file):
                    cpucycle_list_server.append(cpu_cycle)
                    cachemiss_list_server.append(cache_miss)
                    itlbmiss_list_server.append(itlbmiss)
                    dtlbmiss_list_server.append(dtlbmiss)
                elif index is 0:
                    cpucycle_list_cold.append(cpu_cycle)
                    cachemiss_list_cold.append(cache_miss)
                    itlbmiss_list_cold.append(itlbmiss)
                    dtlbmiss_list_cold.append(dtlbmiss)
                else:
                    cpucycle_list_warm.append(cpu_cycle)
                    cachemiss_list_warm.append(cache_miss)
                    itlbmiss_list_warm.append(itlbmiss)
                    dtlbmiss_list_warm.append(dtlbmiss)

    with open(cpu_cycle_file, 'w') as f:
        for elem in cpucycle_list_server:
            f.write(f'{elem}\n')

        f.write(f'\n')
        
        for elem in cpucycle_list_cold:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in cpucycle_list_warm:
            f.write(f'{elem}\n')

    with open(cache_miss_file, 'w') as f:
        for elem in cachemiss_list_server:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in cachemiss_list_cold:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in cachemiss_list_warm:
            f.write(f'{elem}\n')

    with open(itlb_miss_file, 'w') as f:
        for elem in itlbmiss_list_server:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in itlbmiss_list_cold:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in itlbmiss_list_warm:
            f.write(f'{elem}\n')

    with open(dtlb_miss_file, 'w') as f:
        for elem in dtlbmiss_list_server:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in dtlbmiss_list_cold:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in dtlbmiss_list_warm:
            f.write(f'{elem}\n')

def aggregate_cprofile_data(directory, number):
    # pass
    os.makedirs(f'{directory}/../aggregate', exist_ok=True)
    # logging.info(f'directory={directory}')
    # logging.info(f'{os.listdir(directory)}')

    total_time_file = f'{directory}/../aggregate/total-time-{number}'
    server_exec_file = f'{directory}/../aggregate/server-execution-{number}'
    ipc_file = f'{directory}/../aggregate/ipc-{number}'
    daemoncomm_file = f'{directory}/../aggregate/daemoncomm-{number}'
    serialize_file = f'{directory}/../aggregate/serialize-{number}'

    total_time_list_cold = []
    total_time_list_warm = []
    total_time_list_server = []

    server_exec_list_cold = []
    server_exec_list_warm = []
    server_exec_list_server = []

    ipc_list_cold = []
    ipc_list_warm = []
    ipc_list_server = []

    daemoncomm_list_cold = []
    daemoncomm_list_warm = []
    daemoncomm_list_server = []

    serialize_list_cold = []
    serialize_list_warm = []
    serialize_list_server = []

    with open(server_exec_file, 'w+') as f:
        f.seek(0)
        f.truncate()

    with open(ipc_file, 'w+') as f:
        f.seek(0)
        f.truncate()

    with open(daemoncomm_file, 'w+') as f:
        f.seek(0)
        f.truncate()

    with open(serialize_file, 'w+') as f:
        f.seek(0)
        f.truncate()

    for folder in os.listdir(directory):
        folder = f'{directory}/{folder}'
        if os.path.isfile(folder):
            continue
        logging.info(f'folder={folder}')

        if folder.endswith('cprofile'):
            for file in os.listdir(folder):
                file = f'{folder}/{file}'
                logging.info(file)
                if not file.endswith('tottime.log'):
                    continue

                index = get_index(file)
                total_time, server_exec, ipc, daemoncomm, serialize = get_exec_composition(file)
                logging.info(f'{total_time}, {server_exec}, {ipc}, {daemoncomm}, {serialize}')
                if is_server(file):
                    total_time_list_server.append(total_time)
                    server_exec_list_server.append(server_exec)
                    ipc_list_server.append(ipc)
                    daemoncomm_list_server.append(daemoncomm)
                    serialize_list_server.append(serialize)
                elif index is 0:
                    total_time_list_cold.append(total_time)
                    server_exec_list_cold.append(server_exec)
                    ipc_list_cold.append(ipc)
                    daemoncomm_list_cold.append(daemoncomm)
                    serialize_list_cold.append(serialize)
                else:
                    total_time_list_warm.append(total_time)
                    server_exec_list_warm.append(server_exec)
                    ipc_list_warm.append(ipc)
                    daemoncomm_list_warm.append(daemoncomm)
                    serialize_list_warm.append(serialize)

    with open(total_time_file, 'w') as f:
        for elem in server_exec_list_server:
            f.write(f'{elem}\n')

        f.write(f'\n')
        
        for elem in total_time_list_cold:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in total_time_list_warm:
            f.write(f'{elem}\n')

    with open(server_exec_file, 'w') as f:
        for elem in server_exec_list_server:
            f.write(f'{elem}\n')

        f.write(f'\n')
        
        for elem in server_exec_list_cold:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in server_exec_list_warm:
            f.write(f'{elem}\n')

    with open(ipc_file, 'w') as f:
        for elem in ipc_list_server:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in ipc_list_cold:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in ipc_list_warm:
            f.write(f'{elem}\n')

    with open(daemoncomm_file, 'w') as f:
        for elem in daemoncomm_list_server:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in daemoncomm_list_cold:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in daemoncomm_list_warm:
            f.write(f'{elem}\n')

    with open(serialize_file, 'w') as f:
        for elem in serialize_list_server:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in serialize_list_cold:
            f.write(f'{elem}\n')

        f.write(f'\n')

        for elem in serialize_list_warm:
            f.write(f'{elem}\n')

def preprocess_cprofile(directory):
    for folder in os.listdir(directory):
        folder = f'{directory}/{folder}'
        if os.path.isfile(folder):
            continue
        logging.info(f'folder={folder}')

        if folder.endswith('1'):
            aggregate_cprofile_data(folder, 1)
        elif folder.endswith('5'):
            aggregate_cprofile_data(folder, 5)
        elif folder.endswith('10'):
            aggregate_cprofile_data(folder, 10)
        else:
            pass

def preprocess_latency(directory):
    for folder in os.listdir(directory):
        folder = f'{directory}/{folder}'
        if os.path.isfile(folder):
            continue
        logging.info(f'folder={folder}')

        if folder.endswith('1'):
            aggregate_latency_data(folder, 1)
        elif folder.endswith('5'):
            aggregate_latency_data(folder, 5)
        elif folder.endswith('10'):
            aggregate_latency_data(folder, 10)
        else:
            pass
    pass

def preprocess_perf(directory):
    for folder in os.listdir(directory):
        folder = f'{directory}/{folder}'
        if os.path.isfile(folder):
            continue
        logging.info(f'folder={folder}')

        if folder.endswith('1'):
            aggregate_perf_data(folder, 1)
        elif folder.endswith('5'):
            aggregate_perf_data(folder, 5)
        elif folder.endswith('10'):
            aggregate_perf_data(folder, 10)
        else:
            pass
    pass

def preprocess_rusage(directory):
    for folder in os.listdir(directory):
        folder = f'{directory}/{folder}'
        if os.path.isfile(folder):
            continue
        logging.info(f'folder={folder}')

        if folder.endswith('1'):
            aggregate_rusage_data(folder, 1)
        elif folder.endswith('5'):
            aggregate_rusage_data(folder, 5)
        elif folder.endswith('10'):
            aggregate_rusage_data(folder, 10)
        else:
            pass
    pass



if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, \
                        format='[%(asctime)s, %(lineno)d %(funcName)s] %(message)s')
    arg_init()
    logging.info(DIRECTORY)
    for folder in os.listdir(DIRECTORY):
        folder = f'{DIRECTORY}/{folder}'
        if os.path.isfile(folder):
            continue

        logging.info(f'folder={folder}')
        if 'cprofile' in folder:
            preprocess_cprofile(folder)
        elif 'latency' in folder:
            preprocess_latency(folder)
        elif 'perf' in folder:
            preprocess_perf(folder)
        elif 'rusage' in folder:
            preprocess_rusage(folder)
        # else:
        #     raise Exception(f'what folder is this? {folder}')
