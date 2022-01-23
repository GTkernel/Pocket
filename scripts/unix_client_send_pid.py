import socket
import os
import sys
import time
import json

# PERF_SERVER_SOCKET = './sockets/perf_server.sock'
PERF_SERVER_SOCKET = '/sockets/perf_server.sock'


def make_json(pid, events, container_name):
    import json
    args_dict = {}

    args_dict['type']='open-proc-ns'
    args_dict['pid']=pid
    args_dict['events']=events
    args_dict['container_name']=container_name

    args_json = json.dumps(args_dict)

    return args_json

def connect(pid: str, events: list, container_name: str):
    my_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    my_socket.connect(PERF_SERVER_SOCKET)
    json_data_to_send = make_json(pid, events, container_name)
    my_socket.sendall(json_data_to_send.encode('utf-8'))
    data_received = my_socket.recv(1024)
    print(data_received)
    my_socket.close()


if __name__ == '__main__':
    connect(sys.argv[1], sys.argv[2].split(','), sys.argv[3])
