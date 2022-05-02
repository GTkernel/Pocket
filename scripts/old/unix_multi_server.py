import os
import sys
import socket
import errno
import signal
import multiprocessing
import subprocess
import json
import time
from datetime import datetime

SERVER_SOCKET_PATH = './sockets/perf_server.sock'
SERVER_SOCKET: socket.socket
CONCURRENT_CONNECTIONS = 1
MULTIPROC = True

def remove_remaining_sockets():
    pwd = os.getcwd()
    if not os.path.exists(f'{pwd}/sockets'):
        os.makedirs(f'{pwd}/sockets', exist_ok=True)

    if os.path.exists(f'{pwd}/{SERVER_SOCKET_PATH}'):
        os.unlink(SERVER_SOCKET_PATH)

def create_and_bind_sockets():
    global SERVER_SOCKET

    SERVER_SOCKET = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    SERVER_SOCKET.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    SERVER_SOCKET.bind(SERVER_SOCKET_PATH)

def is_target_done(pid: int):
    try:
        os.kill(pid, 0)
    except OSError as err:
        if err.errno == errno.ESRCH: # process does not exist, errno==3
            return True
    return False

def wait_until_process_terminates(pid: int):
    time.sleep(0.1)
    while True:
        if is_target_done(pid):
            break

def run_server():
    SERVER_SOCKET.listen(CONCURRENT_CONNECTIONS)
    while True:
        print('[PERF-SERVER] waiting clients...')
        conn, _addr = SERVER_SOCKET.accept()
        if MULTIPROC: 
            process = multiprocessing.Process(target=handle_client, args=(conn, _addr))
            process.daemon = True
            process.start()
        else:
            handle_client(conn, _addr)

def do_something(pid: int, events: list, container_name: str):
    # print(f'exec perf stat -e {",".join(events)} -p {pid} -o ./data/perf_stat_{container_name}.log')
    timestamp = str(datetime.now()).replace(' ', '-')
    p = subprocess.Popen(f'exec perf stat -e {",".join(events)} -p {pid} -o ./data/perf_stat_{container_name}_{timestamp}.log', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    wait_until_process_terminates(pid)

    try:
        stdout, stderr = p.communicate(timeout=1)
    except:
        p.send_signal(signal.SIGINT)
        stdout, stderr = p.communicate(timeout=1)
    
    with open(f'./data/perf_stat_{container_name}_{timestamp}.log') as f:
        while True:
            line = f.readline()
            print(line, end='')
            if line == '':
                break

def parse_arguments(string: str):
    args_dict = json.loads(string)
    print(args_dict)
    if args_dict['type'] == 'open-proc-ns':
        pass
    elif args_dict['type'] == 'closed-proc-ns':
        container_id = args_dict['cid']
        args_dict['pid'] = subprocess.check_output(f'docker inspect --format=\'{{{{.State.Pid}}}}\' {container_id}', shell=True, encoding='utf-8').strip()
        args_dict['container_name'] = subprocess.check_output(f'docker inspect --format=\'{{{{.Name}}}}\' {container_id}', shell=True, encoding='utf-8').replace('/','').strip()
    return int(args_dict['pid']), args_dict['events'], args_dict['container_name'] 


def handle_client(conn, addr):
    print('[PERF-SERVER] handle client!')
    while True:
        data_received = conn.recv(1024)
        pid, events, container_name = parse_arguments(data_received.decode('utf-8'))
        print(f'pid={pid}, events={events}, container_name={container_name}')
        data_to_send = 'done'.encode('utf-8')
        conn.send(data_to_send)
        do_something(pid, events, container_name)
        break
    conn.close()

def finalize(signum, frame):
    print('[PERF-SERVER] finalizing workers...')
    for process in multiprocessing.active_children():
        # logging.info("Shutting down process %r", process)
        process.terminate()
        process.join()
    sys.exit()

if __name__ == '__main__':
    if os.geteuid() != 0:
        exit("You need to have root privileges to run this script.\nPlease try again, this time using 'sudo'. Exiting.")

    signal.signal(signal.SIGINT, finalize)

    remove_remaining_sockets()
    create_and_bind_sockets()
    run_server()