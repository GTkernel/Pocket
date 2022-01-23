# FROM python:3.6-slim-stretch
FROM ubuntu:bionic

RUN apt-get update -y && \
    # apt-get install -y --fix-missing git wget && \
    # apt-get install -y libgl1-mesa-dev && \
    apt install -y python3.6 python3-pip && \
    # apt-get install -y linux-tools-common linux-tools-generic linux-tools-`uname -r` && \
    python3 -m pip install --upgrade pip setuptools wheel && \
    python3 -m pip install absl-py && \
    python3 -m pip install --upgrade pip && \
    python3 -m pip install sysv_ipc

RUN python3 -m pip install grpcio && \
    python3 -m pip install grpcio-tools && \
    python3 -m pip install protobuf