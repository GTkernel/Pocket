import argparse
import os

def is_num(data):
    try:
        float(data)
        return True
    except ValueError:
        return False

whole_data = {}
iteration = 1

def print_whole_data():
    print('shmem')
    counters = ','.join(whole_data['shmem']['app']['1'].keys())
    avg_dict = dict.fromkeys(whole_data['shmem']['app']['1'].keys(), 0)
    print(f'item,{counters}')
    for entity, e_dict in whole_data['shmem'].items():
        for index, i_dict in e_dict.items():
            counter_values = ','.join(i_dict.values())
            print('%s_%d,' % (entity, int(index)),end='')
            print(counter_values)
            for counter, value in i_dict.items():
                avg_dict[counter] += float(value)
    joined_values = ','.join([str(elem/num) for elem in avg_dict.values()])
    print(f'average,{joined_values}')
    
    print('bin')
    counters = ','.join(whole_data['bin']['app']['1'].keys())
    avg_dict = dict.fromkeys(whole_data['shmem']['app']['1'].keys(), 0)
    print(f'item,{counters}')
    for entity, e_dict in whole_data['shmem'].items():
        for index, i_dict in e_dict.items():
            counter_values = ','.join(i_dict.values())
            print('%s_%d,' % (entity, int(index)),end='')
            print(counter_values)
            for counter, value in i_dict.items():
                avg_dict[counter] += float(value)
    joined_values = ','.join([str(elem/num) for elem in avg_dict.values()])
    print(f'average,{joined_values}')

def write_whole_data_to_file(num, iter):
    with open(f'../n={num},iter={iter}.csv', 'w') as f:
        f.write('shmem\n')
        counters = ','.join(whole_data['shmem']['app']['1'].keys())
        avg_dict = dict.fromkeys(whole_data['shmem']['app']['1'].keys(), 0)
        f.write(f'item,{counters}\n')
        for entity, e_dict in whole_data['shmem'].items():
            for index, i_dict in e_dict.items():
                counter_values = ','.join(i_dict.values())
                f.write('%s_%d,' % (entity, int(index)))
                f.write(counter_values)
                f.write('\n')
                for counter, value in i_dict.items():
                    avg_dict[counter] += float(value)
        joined_values = ','.join([str(elem/num) for elem in avg_dict.values()])
        f.write(f'average,{joined_values}\n')
        
        f.write('bin\n')
        counters = ','.join(whole_data['bin']['app']['1'].keys())
        avg_dict = dict.fromkeys(whole_data['shmem']['app']['1'].keys(), 0)
        f.write(f'item,{counters}\n')
        for entity, e_dict in whole_data['bin'].items():
            for index, i_dict in e_dict.items():
                counter_values = ','.join(i_dict.values())
                f.write('%s_%d,' % (entity, int(index)))
                f.write(counter_values)
                f.write('\n')
                for counter, value in i_dict.items():
                    avg_dict[counter] += float(value)
        joined_values = ','.join([str(elem/num) for elem in avg_dict.values()])
        f.write(f'average,{joined_values}\n')
    
def main():
    global iteration, whole_data

    concurrency = 1
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--dir', type=str, help='specify directory to work')
    parser.add_argument('-i', '--iter', type=int, help='number of iteration')
    args = parser.parse_args()
    directory = args.dir
    iteration = args.iter
    os.chdir(directory)
    try:
        os.mkdir('parsed')
    except:
        pass

    files = os.listdir(os.getcwd())
    files.sort()

    for file_path in files:
        if os.path.isdir(file_path):
            continue

        meta_info = file_path.replace('-', '_').split('_')
        data_channel = meta_info[5]
        entity = meta_info[4]
        index = str(int(meta_info[6]))
        concurrency = max(concurrency, int(index))

        # print(entity, data_channel, index)
        with open(file_path) as f:
            lines = f.readlines()
            for line in lines:
                if line.isspace():
                    continue
                line = line.strip()
                row = line.split()
                if is_num(row[0]) is False:
                    continue

                counter = row[1]

                if row[0].isdigit():
                    value = int(row[0])
                else:
                    value = float(row[0])

                if counter == 'seconds':
                    counter = 'execution_time'

                if data_channel not in whole_data:
                    whole_data[data_channel] = {}
                if entity not in whole_data[data_channel]:
                    whole_data[data_channel][entity] = {}
                if index not in whole_data[data_channel][entity]:
                    whole_data[data_channel][entity][index] = {}
                # if counter not in whole_data[data_channel][entity][index]:
                #     whole_data[data_channel][entity][index][counter] = {}
                
                # print(f'data_channel={data_channel}, entity={entity}, index={index}, counter={counter}, value={value}')
                try:
                    if counter not in whole_data[data_channel][entity][index]:
                        whole_data[data_channel][entity][index][counter] = value
                    else:
                        whole_data[data_channel][entity][index][counter] += value
                except KeyError as e:
                    # print(f'data_channel={data_channel}, entity={entity}, index={index}, counter={counter}, value={value}')
                    # print(row, is_num(row[0]))
                    print('KeyError', e)
                    # print('')
                    # print(f'whole_data[data_channel]={whole_data[data_channel]}')
                    # print('')
                    # print(f'whole_data[data_channel][entity]={whole_data[data_channel][entity]}')
                    # print('')
                    # print(f'whole_data[data_channel][entity][index]={whole_data[data_channel][entity][index]}')
                    # print('')
                    # print(f'whole_data[data_channel][entity][index][counter]={whole_data[data_channel][entity][index][counter]}')
                    # print('')
                    exit(-1)
                # print(line)

    for c, c_d in whole_data.items():
        for e, e_d in c_d.items():
            for i, i_d in e_d.items():
                for c, v in i_d.items():
                    i_d[c] = str(v/iteration)
    # for c, c_d in whole_data.items():
    #     for e, e_d in c_d.items():
    #         for i, i_d in e_d.items():
    #             for c, v in i_d.items():
    #                 print(v)
    # exit()
    # print(iteration)

    # print_whole_data()
    write_whole_data_to_file(concurrency, iteration)



        




if __name__ == '__main__':
    main()