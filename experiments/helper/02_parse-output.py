import os
import sys
import csv
from datetime import datetime

SCRIPTDIR = os.path.dirname(os.path.realpath(__file__))
OUTPUT = sys.stdout
OUTPUTDIR = SCRIPTDIR
FILENAME = None
TIMESTAMP = datetime.now().strftime('%Y%m%d-%H:%M:%S')
RESULT = {}

def main(argv):
    global OUTPUTDIR, FILENAME
    FILENAME=os.path.realpath(argv[1])
    # FILENAME='tmp/20220507-02-00.log'

    OUTPUTDIR = os.path.dirname(os.path.realpath(FILENAME))
    # print(OUTPUTDIR); exit()
    lines = []
    with open(FILENAME) as f:
        start = -1
        for i, line in enumerate(f):
            line = line.strip()

            if line.startswith('(DONE'):
                break
            elif line.startswith('('):
                if len(lines) == 0:
                    lines = [line]
                else:
                    parse_rusage(lines)
                    lines = [line]
            elif len(lines) == 0:
                    continue
            else:
                lines.append(line)
    arrange_data()
    generate_csv()
    # print_pretty_dict(RESULT)


def parse_rusage(lines):
    heading = lines[0][1:-1].split(', ')
    local_result = {}

    platform, app, iter, numinstances = [elem.split('=')[-1] for elem in heading]

    if app not in RESULT:
        RESULT[app] = {}
    if numinstances not in RESULT[app]:
        RESULT[app][numinstances] = {}
    if platform not in RESULT[app][numinstances]:
        RESULT[app][numinstances][platform] = []

    for line in lines[1:]:
        line = line.rstrip()
        if 'inference_time' in line:
            split = line.replace('=', ' ').split(' ')
            model, inference_time = split[5][:-1], split[7]
            model = 'ssdresnet50v1' if model == 'SSDResNetV1' else model
            model = model.lower()
            if model not in local_result:
                local_result[model] = {}
            local_result[model]['inference_time'] = inference_time
        elif 'resource_usage' in line:
            if 'cputime.total' in line:
                split = line.replace('=', ' ').split(' ')
                key, value = split[1], split[2]
            elif 'cputime.user' in line:
                split = line.replace('=', ' ').split(' ')
                key, value = split[1], split[2]
            elif 'cputime.sys' in line:
                split = line.replace('=', ' ').split(' ')
                key, value = split[1], split[2]
            elif 'memory.max_usage' in line:
                split = line.replace('=', ' ').split(' ')
                key, value = split[1], split[2]
            elif 'memory.memsw.max_usage' in line:
                split = line.replace('=', ' ').split(' ')
                key, value = split[1], split[2]
            elif 'memory.stat.pgfault' in line:
                split = line.replace('=', ' ').split(' ')
                key, value = split[1], split[2]
            elif 'memory.stat.pgmajfault' in line:
                split = line.replace('=', ' ').split(' ')
                key, value = split[1], split[2]
            elif 'memory.failcnt' in line:
                split = line.replace('=', ' ').split(' ')
                key, value = split[1], split[2]

            if model not in local_result:
                local_result[model] = {}
            # if key not in local_result[model]:
            #     local_result[model][key] = []
            # local_result[model][key].append(value)
            local_result[model][key] = value

    RESULT[app][numinstances][platform].append(local_result)


def add_inf_result(key, value):
    if key in RESULT:
        RESULT[key].append(value)
    else:
        RESULT[key] = [value]

def arrange_data():
    for app, numinstances in RESULT.items():
        for numinstance, platforms in numinstances.items():
            for platform, local_results in platforms.items():
                aggr_result = {}
                for local_result in local_results:
                    for model, counters in local_result.items():
                        if type(counters) == dict:
                            if model not in aggr_result:
                                aggr_result[model] = {}
                            for counter, measured in counters.items():
                                if counter not in aggr_result[model]:
                                    aggr_result[model][counter] = []
                                aggr_result[model][counter].append(measured)
                        else:
                            aggr_result[model] = counters
                RESULT[app][numinstance][platform] = aggr_result

def generate_csv():
    for app, numinstances in RESULT.items():
        for numinstance, platform, in numinstances.items():
            # print(numinstance, platform)
            generate_csv_per_platform(app, numinstance, platform)
            # exit()

def generate_csv_per_platform(app, numinstance, platform_data):
    # print_pretty_dict(platform_data)
    filename = os.path.basename(FILENAME).split('.')[0]
    filename = f'{filename}_{app}_{numinstance}.csv'
    with open(f'{OUTPUTDIR}/{filename}', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['model', app])
        writer.writerow([])
        for platform, models in platform_data.items():
            writer.writerow(['platform', platform])
            for _, counters in models.items():
                keys = counters.keys()
                values = list(counters.values())
                # values = transpose(values)

                for i, key in enumerate(keys):
                    writer.writerow([key]+values[i])
                # for counter, values in counters.items():
                #     writer.writerow([counter] + values)
                writer.writerow([])

def transpose(oldlist):
    import numpy as np
    oldlist = np.transpose(oldlist).tolist()
    return oldlist

def generate_csv_per_order(working_set, order, platform, data):
    if data == None:
        return

    # print(data)
    filename = 'practice.csv'
    i = 1
    new_data = {}
    be_cpu = data.pop('be_cpu', None)
    be_mem = data.pop('be_mem', None)
    for model, counters in data.items():
    
        for counter, counter_values in counters.items():
            if model not in new_data:
                new_data[model] = {}
            for value in counter_values:
                if counter not in new_data[model]:
                    new_data[model][counter] = []
                new_data[model][counter].append(value)
    data = new_data

    filename = f'{TIMESTAMP}_{working_set}_{order}_{platform}.csv'
    with open(f'{OUTPUTDIR}/{filename}', 'w', newline='') as f:
        writer = csv.writer(f)

        writer.writerow(['inference'])
        writer.writerow(['be_cpu', be_cpu])
        writer.writerow(['be_mem', be_mem])

        for model, counters in data.items():
            counter_values = counters.get('inference_time', None)
            if counter_values != None:
                writer.writerow([model] + counter_values)
        writer.writerow([])

        writer.writerow(['cputime.total'])
        for model, counters in data.items():
            counter_values = counters.get('cputime.total', None)
            if counter_values != None:
                writer.writerow([model] + counter_values)
        writer.writerow([])

        writer.writerow(['memory.max_usage'])
        for model, counters in data.items():
            counter_values = counters.get('memory.max_usage', None)
            if counter_values != None:
                writer.writerow([model] + counter_values)
        writer.writerow([])

        writer.writerow(['memory.max_usage'])
        for model, counters in data.items():
            counter_values = counters.get('memory.max_usage', None)
            if counter_values != None:
                writer.writerow([model] + counter_values)
        writer.writerow([])

        writer.writerow(['memory.stat.pgfault'])
        for model, counters in data.items():
            counter_values = counters.get('memory.stat.pgfault', None)
            if counter_values != None:
                writer.writerow([model] + counter_values)
        writer.writerow([])

def print_pretty_dict(data):
    import json
    print(json.dumps(data, sort_keys=True, indent=4))
    

if __name__ == '__main__':
    main(sys.argv)


# import os
# import sys

# COUNTERLIST = ('inference_time')
# CUR_DIR = os.path.dirname(os.path.realpath(__file__))

# CONTENT='''\
# '''

# RESULTDICT = {}

# def main(args):
#     # parse_result()
#     parse_line()
#     output_result(args[1:])

# def parse_result():
#     if CONTENT.strip() == '':
#         with open(f'{CUR_DIR}/02_latency-rusage.log', 'r') as f:
#             lines = f.readlines()
#     else:
#         lines = CONTENT.splitlines()
#     for line in lines:
#         if line.startswith('[NUMINSTANCES='):
#             policy = line.split(']: ')[-1]
#             RESULTDICT[policy] = {}
#         elif line.startswith('APPLICATION='):
#             application = line.split('=')[-1]
#             RESULTDICT[policy][application] = {}
#         elif line.startswith('    n='):
#             n = line.split('=')[-1]
#             RESULTDICT[policy][application][n] = []
#         elif line.startswith('        i='):
#             i = line.split('=')[-1]
#             new_iter = True
#         elif line == '':
#             new_iter
#         elif 'inference_time' in line:
#             value = line.split('=')[-1]
#             add_inf_result('inference_time', value)
#         elif 'cputime.total' in line:
#             value = line.split('=')[-1]
#             add_inf_result('cputime.total', value)
#         elif 'cputime.user' in line:
#             value = line.split('=')[-1]
#             add_inf_result('cputime.user', value)
#         elif 'cputime.sys' in line:
#             value = line.split('=')[-1]
#             add_inf_result('cputime.sys', value)
#         elif 'memory.max_usage' in line:
#             value = line.split('=')[-1]
#             add_inf_result('memory.max_usage', value)
#         elif 'memory.memsw.max_usage' in line:
#             value = line.split('=')[-1]
#             add_inf_result('memory.memsw.max_usage', value)
#         elif 'memory.stat.pgfault' in line:
#             value = line.split('=')[-1]
#             add_inf_result('memory.stat.pgfault', value)
#         elif 'memory.stat.pgmajfault' in line:
#             value = line.split('=')[-1]
#             add_inf_result('memory.stat.pgmajfault', value)
#         elif 'memory.failcnt' in line:
#             value = line.split('=')[-1]
#             add_inf_result('memory.failcnt', value)
    
# def parse_line():
#     if CONTENT.strip() == '':
#         with open(f'{CUR_DIR}/02_latency-rusage.log', 'r') as f:
#             lines = f.readlines()
#     else:
#         lines = CONTENT.splitlines()

#     for line in lines:
#         line = line.rstrip()
#         if 'inference_time' in line:
#             value = line.split('=')[-1]
#             add_inf_result('inference_time', value)
#         elif 'cputime.total' in line:
#             value = line.split('=')[-1]
#             add_inf_result('cputime.total', value)
#         elif 'cputime.user' in line:
#             value = line.split('=')[-1]
#             add_inf_result('cputime.user', value)
#         elif 'cputime.sys' in line:
#             value = line.split('=')[-1]
#             add_inf_result('cputime.sys', value)
#         elif 'memory.max_usage' in line:
#             value = line.split('=')[-1]
#             add_inf_result('memory.max_usage', value)
#         elif 'memory.memsw.max_usage' in line:
#             value = line.split('=')[-1]
#             add_inf_result('memory.memsw.max_usage', value)
#         elif 'memory.stat.pgfault' in line:
#             value = line.split('=')[-1]
#             add_inf_result('memory.stat.pgfault', value)
#         elif 'memory.stat.pgmajfault' in line:
#             value = line.split('=')[-1]
#             add_inf_result('memory.stat.pgmajfault', value)
#         elif 'memory.failcnt' in line:
#             value = line.split('=')[-1]
#             add_inf_result('memory.failcnt', value)

# def add_inf_result(key, value):
#     if key in RESULTDICT:
#         RESULTDICT[key].append(value)
#     else:
#         RESULTDICT[key] = [value]

# def output_result(key = None):
#     key = RESULTDICT.keys() if len(key) == 0 else key
#     for k, v in RESULTDICT.items():
#         if k in key:
#             print(k)
#             print('\n'.join(v))
#             # if CONTENT.strip() == '':
#             #     print('\n'.join(v))
#             # else:
#             #     print(''.join(v), end='')
#             print('')

# if __name__ == '__main__':
#     main(sys.argv)