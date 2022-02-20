FROM ubuntu:bionic

ENV POCKET_CLIENT True

RUN apt-get update -y && \
    apt install -y python3.6 python3-pip && \
    # python3 -m pip install --upgrade pip setuptools wheel && \
    python3 -m pip install absl-py && \
    python3 -m pip install --upgrade pip && \
    python3 -m pip install sysv_ipc numpy
