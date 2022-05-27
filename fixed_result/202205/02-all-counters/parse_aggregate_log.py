import os
import sys

datatype = float if os.environ.get('INFERENCE', '0') == '1' else int
# datatype = float

def main(argv):
    filename = os.path.realpath(argv[1])
    result = parse_file(filename)
    print_result(result)

def parse_file(filename):
    result = {}
    with open(filename, 'r') as f:
        for line in f:
            if line.startswith('(platform'):
                split = line[1:-2].split(', ')
                platform, app, iteration, num = [elem.split('=')[-1] for elem in split]
                linecounter = 1
            else:
                split = line.replace('=', ' ').split()
                # print(split, file=sys.stderr)
                if datatype == float:
                    counter, value = split[6:]
                else:
                    counter, value = split[1:]

                if app not in result:
                    result[app] = {}
                if num not in result[app]:
                    result[app][num] = {}
                if counter not in result[app][num]:
                    result[app][num][counter] = {}

                if platform == 'monolithic':
                    if 'mono' not in result[app][num][counter]:
                        result[app][num][counter]['mono'] = 0
                    result[app][num][counter]['mono'] += datatype(value)
                else:
                    if linecounter == 1:
                        if counter == 'inference_time':
                            linecounter += 1
                            continue
                        if 'be' not in result[app][num][counter]:
                            result[app][num][counter]['be'] = 0
                        result[app][num][counter]['be'] += datatype(value)
                    else:
                        if 'fe' not in result[app][num][counter]:
                            result[app][num][counter]['fe'] = 0
                        result[app][num][counter]['fe'] += datatype(value)
                    linecounter += 1
    return result
    
def print_result(result):
    for app, nums in result.items():
        for  num, counters in nums.items() :
            for counter, plfs in counters.items():
                for plf, value in plfs.items():
                    print(f'{app} {num} {counter} {plf} {value}')

if __name__ == '__main__':
    main(sys.argv)