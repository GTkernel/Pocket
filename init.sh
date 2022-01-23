#!/bin/bash

cp $HOME/yolov3.weights scripts
cp $HOME/yolov3.weights yolov3-tf2/data

conda install -y grpcio
conda install -y grpcio-tools

pushd .
cd tfrpc/proto
bash gen_proto.sh
popd

$HOME/cc/anaconda/bin/pip install opencv-python==4.1.1.26 tensorflow==2.1.0rc1 absl-py
python convert.py
git checkout experiments

git clone https://github.com/whalepark/yolov3-tf2 yolov3-tf2-mono
cd yolov3-tf2-mono
git checkout monolith-nobox