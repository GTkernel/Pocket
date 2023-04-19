import os
import sys
import subprocess
import shlex
import sysv_ipc

def main(args):
    path = os.path.dirname(os.path.abspath(__file__))
    os.chdir(path)
    
    mq_key = 20210131
    mq = sysv_ipc.MessageQueue(mq_key, sysv_ipc.IPC_CREX, mode=0o606)
    data, _ = mq.receive()
    data = data.decode().split()
    instance_name = data[0]
    checkpoint_name = data[1]
    
    command = f'docker checkpoint create {instance_name} {checkpoint_name}'
    command = shlex.split(command)
    completed_process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    # print('hello', completed_process.stdout.decode())
    
    # command = f'docker commit {instance_name}'
    # command = shlex.split(command)
    # completed_process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    # # print('stdout', completed_process.stdout.decode())
    # id = completed_process.stdout.decode().split(':')[1]
    
    # for i in range(1, num + 1):
    #     instance_to_create = f'{app}-monolithic-{i:04}'
    #     # print(instance_to_create)
    #     # continue
    #     command = f'docker create --volumes-from {app}-monolithic-0000 --name {instance_to_create} {id}'
    #     command = shlex.split(command)
    #     completed_process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    #     print('stdout', completed_process.stdout.decode())
    
    mq.send('well-done')
    mq.remove()
    # data, _ = mq.receive()
        
if __name__ == '__main__':
    main(sys.argv)