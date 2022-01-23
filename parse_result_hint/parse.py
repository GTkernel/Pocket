import os
import sys
import shutil

Image = True

def main(args):
    global Image
    working_dir = os.getcwd()
    script_dir = os.path.dirname(os.path.realpath(__file__))

    if script_dir != working_dir:
        print('WARNING: move working directory to script directory')
        os.chdir(script_dir)

    if len(args) < 2:
        print('ERROR: target directory not specified')
        sys.exit(-1)

    dir = args[1]
    if len(args) > 2:
        Image = str(args[2])


    arrange_files(dir)
    make_summary(dir)


def arrange_files(dir):
    prefix = os.path.abspath(f'../{dir}/data')
    mon = f'{prefix}/mon'
    poc = f'{prefix}/poc'

    clean_up(prefix)
    mon_arrange(mon)
    poc_arrange(poc)

def make_summary(dir):
    prefix = os.path.abspath(f'../{dir}/data')
    summary_path = f'{prefix}/summary'
    mon_summary_path = f'{summary_path}/mon'
    poc_summary_path = f'{summary_path}/poc'
    mon_path = f'{prefix}/mon'
    poc_path = f'{prefix}/poc'

    os.makedirs(mon_summary_path, exist_ok=True)
    os.makedirs(poc_summary_path, exist_ok=True)

    for f in abslistdir(os.listdir(mon_summary_path), mon_summary_path):
        try:
            os.remove(f)
        except IsADirectoryError:
            shutil.rmtree(f, ignore_errors=True)

    for f in abslistdir(os.listdir(poc_summary_path), poc_summary_path):
        try:
            os.remove(f)
        except IsADirectoryError:
            shutil.rmtree(f, ignore_errors=True)


    mon_summary(mon_summary_path, mon_path)
    poc_summary(poc_summary_path, poc_path)

def clean_up(dir):
    files = abslistdir(os.listdir(dir), dir)
    files.sort()
    # print(dirs)
    for file in files:
        if os.path.basename(file) not in ('mon', 'poc', 'summary'):
            os.removedirs(file)

def mon_arrange(mon):
    instances = (1, 5, 10)
    # instances = (1, 3, 5, 10)
    for instance in instances:
        path = f'{mon}/{instance}'
        # N * counters(4) * iter
        how_many_files = instance * 4 * 3
        how_many_pf = instance * 3
        how_many_0 = instance * 3
        how_many_3 = instance * 3
        how_many_4 = instance * 3

        raw_files = abslistdir(os.listdir(path), path)
        raw_files = list((filter(lambda f: f.endswith('.log'), raw_files)))
        raw_files.sort()

        files_pf = list(filter(lambda f: f.endswith('-PF.log'), raw_files))
        files_0  = list(filter(lambda f: f.endswith('-0.log'), raw_files))
        files_3  = list(filter(lambda f: f.endswith('-3.log'), raw_files))
        files_4  = list(filter(lambda f: f.endswith('-4.log'), raw_files))

        if len(files_0) == 0:
            how_many_0 = 0
            return
        if len(files_3) == 0:
            how_many_3 = 0
            return
        if len(files_4) == 0:
            how_many_4 = 0
            return

        assert len(files_0) == how_many_0
        assert len(files_3) == how_many_3
        assert len(files_4) == how_many_4

        files_pf.sort()
        files_0.sort()
        files_3.sort()
        files_4.sort()

        files_pf = files_pf[:how_many_pf]
        files_dict = {
            'pf': files_pf,
            '0': files_0,
            '3': files_3,
            '4': files_4,
        }

        counters = files_dict.keys()
        for counter in counters:
            counter_path = f'{path}/{counter}'
            os.makedirs(counter_path, exist_ok=True)
            for f in abslistdir(os.listdir(counter_path), counter_path):
                # print(f'remove {f}')
                os.remove(f)

            for f in files_dict[counter]:
                # print(f'copy {f}')
                shutil.copy(src=f, dst = counter_path)
    

def poc_arrange(poc):
    instances = (1, 3, 5, 10)
    for instance in instances:
        path = f'{poc}/{instance}'
        # N * counters(4) * iter
        how_many_files = instance * 3
        how_many_pf = 3
        how_many_0 =  3
        how_many_3 =  3
        how_many_4 =  3

        raw_files = abslistdir(os.listdir(path), path)
        raw_files = list((filter(lambda f: f.endswith('.log'), raw_files)))
        raw_files.sort()

        num_files = len(raw_files)
        half = int(num_files/2)

        assert num_files % 2 == 0

        files_pf = list(filter(lambda f: f.endswith('-PF.log'), raw_files))
        files_0  = list(filter(lambda f: f.endswith('-0.log'), raw_files))
        files_3  = list(filter(lambda f: f.endswith('-3.log'), raw_files))
        files_4  = list(filter(lambda f: f.endswith('-4.log'), raw_files))

        dynamic_files = files_pf[:3] + files_0[:3] + files_3[:3] + files_4[:3]
        static_files  = files_pf[3:] + files_0[3:] + files_3[3:] + files_4[3:]

        dyn_files_dict = {
            'dyn': dynamic_files,
            'sta': static_files
        }

        for dir in ('dyn', 'sta'):
            dynpath = f'{poc}/{dir}/{instance}'
            os.makedirs(dynpath, exist_ok=True)
            for f in abslistdir(os.listdir(dynpath), dynpath):
                # print(f)
                try:
                    os.remove(f)
                except IsADirectoryError:
                    shutil.rmtree(f, ignore_errors=True)

            # print(dyn_files_dict[dir])
            for f in dyn_files_dict[dir]:
                shutil.copy(src=f, dst = dynpath)

            # print(f'dynpath={dynpath}')
            # continue

            files_pf = list(filter(lambda f: f.endswith('-PF.log'), dyn_files_dict[dir]))
            files_0  = list(filter(lambda f: f.endswith('-0.log'), dyn_files_dict[dir]))
            files_3  = list(filter(lambda f: f.endswith('-3.log'), dyn_files_dict[dir]))
            files_4  = list(filter(lambda f: f.endswith('-4.log'), dyn_files_dict[dir]))

            # print(files_pf)
            # exit()

            assert len(files_0) == how_many_0
            assert len(files_3) == how_many_3
            assert len(files_4) == how_many_4

            files_pf.sort()
            files_0.sort()
            files_3.sort()
            files_4.sort()

            files_pf = files_pf[:how_many_pf]
            files_dict = {
                'pf': files_pf,
                '0': files_0,
                '3': files_3,
                '4': files_4,
            }

            counters = files_dict.keys()
            for counter in counters:
                counter_path = f'{dynpath}/{counter}'
                os.makedirs(counter_path, exist_ok=True)
                for f in abslistdir(os.listdir(counter_path), counter_path):
                    # print(f'remove {f}')
                    os.remove(f)

                for f in files_dict[counter]:
                    # print(f'copy {f}')
                    shutil.copy(src=f, dst = counter_path)

def mon_summary(summary_path, data_path):
    instances = (1, 5, 10)
    # instances = (1, 3, 5, 10)
    for ins in instances:
        instance_path= f'{data_path}/{ins}'
        counters = ('0', '3', '4', 'pf')
        for counter in counters:
            counter_path = f'{instance_path}/{counter}'
            # print('')
            pre_parsed = []
            for file in abslistdir(os.listdir(counter_path), counter_path):
                # print(f'{file}')
                pre_parsed += open(file, 'r').readlines()

            for i, line in enumerate(pre_parsed.copy()):
                line = line.lstrip()
                line = line.replace(',', '\t')
                pre_parsed[i] = line

            if '' in pre_parsed:
                pre_parsed.remove('')
            if '\n' in pre_parsed:
                pre_parsed.remove('\n')
            
            # print(f'n={ins}')
            filepath = f'{summary_path}/n={ins:2}_c={counter}.summary'
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w') as f:
                f.writelines(pre_parsed)
    generate_summary(summary_path)
    
def poc_summary(summary_path, data_path):
    instances = (1, 5, 10)
    # instances = (1, 3, 5, 10)
    for dyn in ('dyn', 'sta'):
        for ins in instances:
            instance_path= f'{data_path}/{dyn}/{ins}'
            os.makedirs(instance_path, exist_ok=True)
            counters = ('0', '3', '4', 'pf')
            for counter in counters:
                counter_path = f'{instance_path}/{counter}'
                os.makedirs(counter_path, exist_ok=True)

                # print('')
                pre_parsed = []
                for file in abslistdir(os.listdir(counter_path), counter_path):
                    # print(f'{file}')
                    if Image is True:
                        pre_parsed += open(file, 'r').readlines()[10:]
                    else:
                        pre_parsed += open(file, 'r').readlines()[1:]

                    if len(pre_parsed) == 0:
                        print(Image)
                        print('>>>>>', file)
                        print(open(file, 'r').readlines())
                        print()
                        print()

                for i, line in enumerate(pre_parsed.copy()):
                    line = line.lstrip()
                    line = line.replace(',', '\t')
                    pre_parsed[i] = line

                if '' in pre_parsed:
                    pre_parsed.remove('')
                if '\n' in pre_parsed:
                    pre_parsed.remove('\n')
                
                # print(f'n={ins}')
                filepath = f'{summary_path}/{dyn}/n={ins:2}_c={counter}.summary'
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, 'w') as f:
                    f.writelines(pre_parsed)

        generate_summary(f'{summary_path}/{dyn}')

def generate_summary(path):
    for fpath in abslistdir(os.listdir(path), path):
        with open(fpath, 'r') as f:
            fileline = f.readlines()
        
        length = len(fileline)
        toten = int(length/10) + 1

        index = 0
        summary = f'{path}/sum_{os.path.basename(fpath)}'
        last = False
        while True:
    
            if length - index <= 10:
                left = length - index
                lines = [oneline.split() for oneline in fileline[index:index+left]]
                last = True
            else:
                lines = [oneline.split() for oneline in fileline[index:index+10]]

            sum1, sum2 = 0, 0
            for line in lines:
                num1, num2 = line
                sum1 += int(num1)
                sum2 += int(num2)


            index += 10
            with open(summary, 'a') as summary_f:
                summary_f.write(f'{sum1}\t{sum2}\n')

            if last:
                break
    

def abslistdir(filelist, prefix):
    new_filelist = [os.path.abspath(f'{prefix}/{file}') for file in filelist]
    return new_filelist

if __name__ == '__main__':
    main(sys.argv)