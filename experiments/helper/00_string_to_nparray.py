import os
import sys

STRING='''\
0.058420471
0.07253003
0.071421037
0.093604339
0.102158247
0.038843539
0.041557612
0.043382235
0.035218657
0.097796525
0.140788751
0.109211941
0.097834154
0.121737124
0.115518496
0.018711603
0.029736104
0.030113449
0.033993587
0.030053162
0.016334453
0.014115165
0.012423671
0.014968524
0.012177039
0.066874446
0.078512861
0.118214989
0.070755385
0.134860805
0.064213892
0.038269693
0.046471526
0.033321498
0.048546696
'''

ORIENTATION='vertical'
# STRING='''\
# mobilenetv2,7387014300,7198421432,7366436180,7325945741,7359104945
# resnet50,13078156235,13033416231,12717408752,12806932383,12514055126
# ssdmobilenetv2,23835644794,25994652380,25637330204,24937794914,24044948876
# ssdresnet50v1,73960568056,75549961478,73482396679,74945559606,72054290312
# smallbert,19753793820,19148553791,19097111447,19620561003,18682216105
# talkingheads,54318227635,56886385693,55617421793,56005950142,55922643321
# '''
# ORIENTATION='horizontal'
SPLITTER=None
# SPLITTER=','

def main(argv):
    global STRING
    STRING = STRING.replace(',', '')
    if ORIENTATION == 'vertical':
        vertical_parsing()
    else:
        horizontal_parsing()

def vertical_parsing():
    lines = STRING.split('\n')
    columns = []
    for line in lines:
        split = line.split(SPLITTER)
        for i, elem in enumerate(split):
            while i + 1 > len(columns):
                columns.append([])
            # if elem.isdigit():
            #     elem = int(elem)
            # else:
            #     elem = float(elem)
            columns[i].append(elem)

    make_list_to_nparray(columns)

def horizontal_parsing():
    lines = STRING.split('\n')
    rows = []
    for line in lines:
        split = line.split(SPLITTER)
        if len(split) == 0:
            continue
        rows.append(split)
    make_list_to_nparray(rows)

def make_list_to_nparray(lists):
    for list in lists:
        # prefix=' = np.array(('
        prefix='np.array(('
        suffix='))'
        print(prefix, end='')
        print(', '.join(list), end='')
        print(suffix)


if __name__ == '__main__':
    main(sys.argv)