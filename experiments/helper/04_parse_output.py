import os
import sys
import csv
from datetime import datetime

SCRIPTDIR = os.path.dirname(os.path.realpath(__file__))
OUTPUT = sys.stdout
OUTPUTDIR = SCRIPTDIR
TIMESTAMP = datetime.now().strftime('%Y%m%d-%H:%M:%S')
RESULT = {}

def main(argv):
    global OUTPUTDIR
    # filename=argv[1]
    filename='tmp/20220507-04-03.log'

    OUTPUTDIR = os.path.dirname(os.path.realpath(filename))
    # print(OUTPUTDIR); exit()
    lines = []
    with open(filename) as f:
        start = -1
        for i, line in enumerate(f):
            line = line.strip()

            if line.startswith('('):
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


def parse_rusage(lines):
    heading = lines[0][1:-1].split(', ')
    local_result = {}
    app_list = []

    workset, order, platform, _ = [elem.split('=')[-1] for elem in heading]
    app_index = 0 if platform == 'monolithic' else -1

    if workset not in RESULT:
        RESULT[workset] = {}
    if platform not in RESULT[workset]:
        RESULT[workset][platform] = {}
    if order not in RESULT[workset][platform]:
        RESULT[workset][platform][order] = []

    for line in lines[1:]:
        if 'APPLICATIONS' in line:
            app_list = line[14:-1].split()
            app_list.insert(0, 'backend')
        elif 'POCKET_BE_CPU' in line:
            be_cpu = line.split('=')[-1]
            local_result['be_cpu'] = be_cpu
        elif 'POCKET_BE_MEM=' in line:
            be_mem = line.split('=')[-1]
            local_result['be_mem'] = be_mem
        elif 'inference_time' in line:
            split = line.replace('=', ' ').split(' ')
            model, inference_time = split[5][:-1], split[7]
            model = 'ssdresnet50v1' if model == 'SSDResNetV1' else model
            model = model.lower()

            if model not in local_result:
                local_result[model] = {}
            # if 'inference_time' not in local_result[model]:
            #     local_result[model]['inference_time'] = []

            # local_result[model]['inference_time'].append(inference_time)
            local_result[model]['inference_time'] = inference_time
        elif 'resource_usage' in line:
            if 'cputime.total' in line:
                app_index += 1
            try:
                model = app_list[app_index]
            except:
                print(app_list)
                print(app_index)
                raise Exception('Exception')

            split = line.replace('=', ' ').split(' ')
            key, value = split[1], split[2]

            if model not in local_result:
                local_result[model] = {}
            # if key not in local_result[model]:
            #     local_result[model][key] = []
            # local_result[model][key].append(value)
            local_result[model][key] = value

    RESULT[workset][platform][order].append(local_result)

def arrange_data():
    for working_set, platforms in RESULT.items():
        for platform, orders in platforms.items():
            for order, local_results in orders.items():
                aggr_result = {}
                for local_result in local_results:
                    for key, value in local_result.items():
                        if type(value) == dict:
                            if key not in aggr_result:
                                aggr_result[key] = {}
                            for counter, measured in value.items():
                                if counter not in aggr_result[key]:
                                    aggr_result[key][counter] = []
                                aggr_result[key][counter].append(measured)
                        else:
                            aggr_result[key] = value
                RESULT[working_set][platform][order] = aggr_result

def generate_csv():
    for working_set, data in RESULT.items():
        forward_data = data.get('pocket', None)
        backward_data = data.get('monolithic', None)
        generate_csv_per_platform(working_set, 'pocket', forward_data)
        generate_csv_per_platform(working_set, 'monolithic', backward_data)

def generate_csv_per_platform(working_set, order, data):
    if data == None:
        return
    
    pocket_data = data.get('regular', None)
    monolithic_data = data.get('reversed', None)

    generate_csv_per_order(working_set, order, 'regular', pocket_data)
    generate_csv_per_order(working_set, order, 'reversed', monolithic_data)

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

    

if __name__ == '__main__':
    main(sys.argv)