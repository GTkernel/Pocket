#!/bin/bash

rm -f ../client/{yolo_pb2_grpc.py,yolo_pb2.py}
rm -f ../server/{yolo_pb2_grpc.py,yolo_pb2.py}

python3 -m grpc_tools.protoc -I. --python_out=../server --grpc_python_out=../server yolo.proto
python3 -m grpc_tools.protoc -I. --python_out=../client --grpc_python_out=../client yolo.proto

# SRC_DIR=.
# SERVER_DST_DIR=../server

# protoc -I=$SRC_DIR --cpp_out=$SERVER_DST_DIR $SRC_DIR/yolo.proto
# protoc -I=$SRC_DIR --grpc_out=$SERVER_DST_DIR --plugin=protoc-gen-grpc=`which grpc_cpp_plugin` $SRC_DIR/yolo.proto

# cd ../server
# make