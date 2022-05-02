import sys
import os

ROOT = ''

def init():
    global ROOT
    ROOT = os.path.dirname(os.path.abspath(__file__))

if __name__ == '__main__':
    init()
    for folder in os.listdir(ROOT):
        abs_folder = f'{ROOT}/{folder}'
        if os.path.isfile(abs_folder):
            continue

        os.system(f'cd {folder} && pwd && ls -al')

        if folder.endswith('_mon'):
            new_name = abs_folder[:-4]
            os.rename(abs_folder, new_name)
            folder = new_name
            abs_folder = new_name

        for num in os.listdir(abs_folder):
            abs_num = f'{abs_folder}/{num}'

            os.system(f'cd {abs_num} && pwd && ls -al')

            for iteration in os.listdir(abs_num):
                abs_iteration = f'{abs_num}/{iteration}'
                if iteration.endswith('-monolithic'):
                    new_iter_name = abs_iteration[:-11]
                    os.rename(abs_iteration, new_iter_name)
                elif iteration.endswith('-mononlithic'):
                    new_iter_name = abs_iteration[:-12]
                    os.rename(abs_iteration, new_iter_name)