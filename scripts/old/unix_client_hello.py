import socket
import os
import sys
import time

def connect():
    my_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    my_socket.connect('./sockets/server.sock')
    data=f'{os.getpid()}'.encode('utf-8')
    my_socket.sendall(data)
    # result = my_socket.recv(1024)
    # print(result)
    time.sleep(5)
    my_socket.close()


if __name__ == '__main__':
    connect()
