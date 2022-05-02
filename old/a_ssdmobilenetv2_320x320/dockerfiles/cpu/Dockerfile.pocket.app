FROM ubuntu:bionic

ENV POCKET_CLIENT True

RUN apt-get update -y && \
    apt install -y python3.6 python3-pip git && \
    # python3 -m pip install --upgrade pip setuptools wheel && \
    python3 -m pip install absl-py && \
    python3 -m pip install --upgrade pip && \
    python3 -m pip install sysv_ipc numpy && \
    python3 -m pip install Pillow && \
    python3 -m pip install numpy

ADD obj_det_sample_img /test_images