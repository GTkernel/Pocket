#!/bin/bash

BASEDIR=$(dirname $0)
NUMINSTANCE=1
TMPFS=0
function parse_arg() {
    for arg in $@; do
        case $arg in
            -n=*|--num=*)
                NUMINSTANCE="${arg#*=}"
                ;;
            -t=*|--tmpfs=*)
                TMPFS=1
                ;;
        esac
    done
}

function help() {
    echo Usage: ./exp_script COMMAND [OPTIONS]
}

function build_image() {
    docker rmi ubench_grpc_vs_lipc ubench_grpc_vs_lipc/server ubench_grpc_vs_lipc/client
    # docker rmi ubench_grpc_vs_lipc/server ubench_grpc_vs_lipc/client

    docker image build -t ubench_grpc_vs_lipc -f dockerfiles/Dockerfile .
    docker image build -t ubench_grpc_vs_lipc/server -f dockerfiles/Dockerfile.server .
    docker image build -t ubench_grpc_vs_lipc/client -f dockerfiles/Dockerfile.client .
}

function build_proto() {
    rm -f client/{exp_pb2_grpc.py,exp_pb2.py}
    rm -f server/{exp_pb2_grpc.py,exp_pb2.py}

    python3 -m grpc_tools.protoc -I. --python_out=server --grpc_python_out=server proto/exp.proto
    python3 -m grpc_tools.protoc -I. --python_out=client --grpc_python_out=client proto/exp.proto
}

# function _run_server() {

# }

function run() {
    # Add this to perf profiling.
        # --cap-add SYS_ADMIN \
        # --cap-add IPC_LOCK \
    local file=$1

    docker rm -f $(docker ps -a | grep "server\|client" | awk '{print $1}') > /dev/null 2>&1
    docker network rm exp_net
    docker network create --driver=bridge exp_net

    
    docker run -d \
               --network=exp_net \
               --name=server \
               --privileged \
               --volume=$(pwd)/server:/server \
               --volume=/var/lib/docker/overlay2:/layers \
               --volume=/var/run/docker.sock:/var/run/docker.sock \
               --workdir='/server' \
               --ipc=shareable \
               ubench_grpc_vs_lipc/server:latest \
               python3 server.py
    
    docker run \
            --network=exp_net \
            --name=client \
            --volume=$(pwd)/client:/client \
            --workdir='/client' \
            --env SERVER_ADDR=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' server) \
            --ipc=container:server \
            ubench_grpc_vs_lipc/client:latest \
            python3 client.py --file $file #/imgs/street.jpg

    docker logs server

    docker rm -f $(docker ps -a | grep "server\|client" | awk '{print $1}') > /dev/null 2>&1
}


function init_tmpfs() {
    local dir="$(pwd)/tmpfs/"
    echo "${dir}"

    sudo umount "${dir}"
    sudo rm -rf "${dir}"

    if [[ ! -d "${dir}" ]]; then
        sudo mkdir -p "${dir}"
        sudo mount --make-shared "${dir}"
        sudo mount --make-shared -t tmpfs -o size=100M tmpfs "${dir}"
        sudo cp imgs/street.jpg "${dir}"
        sudo cp imgs/photographer.jpg "${dir}"
    fi
}

function run_tmpfs() {
    # Add this to perf profiling.
        # --cap-add SYS_ADMIN \
        # --cap-add IPC_LOCK \

    docker rm -f $(docker ps -a | grep "server\|client" | awk '{print $1}') > /dev/null 2>&1
    docker network rm exp_net
    docker network create --driver=bridge exp_net

    
    docker run -d \
               --network=exp_net \
               --name=server \
               --privileged \
               --volume=$(pwd)/server:/server \
               --volume=/var/lib/docker/overlay2:/layers \
               --volume=/var/run/docker.sock:/var/run/docker.sock \
               --volume=$(pwd)/tmpfs:/tmpfs \
               --workdir='/server' \
               ubench_exp_grpc/server:latest \
               python3 server.py

    docker run \
            --network=exp_net \
            --name=client \
            --volume=$(pwd)/client:/client \
            --volume=$(pwd)/tmpfs:/tmpfs \
            --workdir='/client' \
            --env SERVER_ADDR=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' server) \
            ubench_exp_grpc/client:latest \
            python3 client.py --file /tmpfs/street.jpg

    docker logs server
    docker rm -f $(docker ps -a | grep "server\|client" | awk '{print $1}') > /dev/null 2>&1
}

function run_tmpfs_large() {
    # Add this to perf profiling.
        # --cap-add SYS_ADMIN \
        # --cap-add IPC_LOCK \

    docker rm -f $(docker ps -a | grep "server\|client" | awk '{print $1}') > /dev/null 2>&1
    docker network rm exp_net
    docker network create --driver=bridge exp_net

    
    docker run -d \
               --network=exp_net \
               --name=server \
               --privileged \
               --volume=$(pwd)/server:/server \
               --volume=/var/lib/docker/overlay2:/layers \
               --volume=/var/run/docker.sock:/var/run/docker.sock \
               --volume=$(pwd)/tmpfs:/tmpfs \
               --workdir='/server' \
               ubench_exp_grpc/server:latest \
               python3 server.py

    docker run \
            --network=exp_net \
            --name=client \
            --volume=$(pwd)/client:/client \
            --volume=$(pwd)/tmpfs:/tmpfs \
            --workdir='/client' \
            --env SERVER_ADDR=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' server) \
            ubench_exp_grpc/client:latest \
            python3 client.py --file /tmpfs/street.jpg

    docker logs server
    docker rm -f $(docker ps -a | grep "server\|client" | awk '{print $1}') > /dev/null 2>&1
}

cd $BASEDIR
COMMAND=$([[ $# == 0 ]] && echo help || echo $1)
parse_arg ${@:2}
case $COMMAND in
    image)
        build_image
        ;;
    proto)
        build_proto
        ;;
    run)
        build_proto
        run /imgs/street.jpg
        ;;
    run-large)
        build_proto
        run /imgs/photographer.jpg
        ;;
    run-tmpfs)
        build_proto
        init_tmpfs
        run_tmpfs
        ;;
    run-tmpfs-large)
        build_proto
        init_tmpfs
        run_tmpfs
        ;;
    # generic-run)

    *|help)
        help
        ;;
esac



## Ref
# https://pixabay.com/photos/architecture-new-york-city-manhattan-1853552/