#!/bin/bash

BASEDIR=$(dirname $0)
cd $BASEDIR
NUMINSTANCES=1
TIMESTAMP=$(date +%Y%m%d-%H:%M:%S)
NETWORK=tf-grpc-exp
RSRC_RATIO=0.5
INTERVAL=0
RSRC_REALLOC=1
PHYS_CPU_BIND=0
FPS=5

EXP_ROOT="${HOME}/settings/tf-slim/lightweight/pjt/grpc"
SUBNETMASK=111.222.0.0/16
SERVER_IP=111.222.3.26
TMP_FOR_MEASURE=tmp-for-measure
PERF_COUNTERS=cpu-cycles,page-faults,minor-faults,major-faults,cache-misses,LLC-load-misses,LLC-store-misses,dTLB-load-misses,iTLB-load-misses,instructions


mkdir -p data

source internal_functions.sh

function parse_arg() {
    for arg in $@; do
        case $arg in
            -n=*|--num=*)
                NUMINSTANCES="${arg#*=}"
                ;;
            -s=*|--server=*)
                SERVER="${arg#*=}"
                ;;
            -ri=*|--random-interval=*)
                INTERVAL="${arg#*=}"
                # This option should be deprecated.
                ;;
            -r=*|--ratio=*)
                RSRC_RATIO="${arg#*=}"
                ;;
            -ra=*|--resource-realloc=*)
                RSRC_REALLOC="${arg#*=}"
                ;;
            -b=*|--physcpubind=*)
                PHYS_CPU_BIND="${arg#*=}"
                set_cgroup
                ;;
            --fps=*)
                FPS="${arg#*=}"
                ;;
            -b=*|--physcpubind=*)
                PHYS_CPU_BIND="${arg#*=}"
                set_cgroup
                ;;
        esac
    done
}

function generate_rand_num() {
    local upto=$1
    if [[ "$INTERVAL" = "1" ]]; then
        local base=$(printf "0.%01d\n" $(( RANDOM % 1000 )))
        # echo ${#base}
        echo "${base} * ${upto}" | bc
    else
        echo 1.5
    fi
}

function util_get_running_time() {
    local container_name=$1
    # local start=$(docker inspect --format='{{.State.StartedAt}}' $container_name | xargs date +%s.%N -d)
    local start=$(cat ${TMP_FOR_MEASURE}/start_${container_name})
    local end=$(docker inspect --format='{{.State.FinishedAt}}' $container_name | xargs date +%s.%N -d)
    local running_time=$(echo $end - $start | tr -d $'\t' | bc)

    echo $running_time
}

function util_logging_latency_start() {
    local container_name=$1
    date +%s.%N > ${TMP_FOR_MEASURE}/start_${container_name}
}

function utils_postprocess_server_rsuage_metric() {
    local file_path=$1
    # echo $file_path
    # cat $file_path
    # echo ================
    IFS='=' pagefault_init_arr=($(cat $file_path | grep pagefault_init | grep -v major))
    IFS='=' pagefault_arr=($(cat $file_path | grep pagefault | grep -v major | grep -v init))
    pagefault=$(bc <<< "${pagefault_arr[1]} - ${pagefault_init_arr[1]}")
    # echo ${pagefault_init[1]} $pagefault #$(bc <<< "${pagefault[1]} - ${pagefault_init[1]}")
    IFS='=' major_pagefault_init_arr=($(cat $file_path | grep major_pagefault_init))
    IFS='=' major_pagefault_arr=($(cat $file_path | grep major_pagefault | grep -v init))
    major_pagefault=$(bc <<< "${major_pagefault_arr[1]} - ${major_pagefault_init_arr[1]}")
    # echo $major_pagefault_init $major_pagefault # $(bc <<< "${major_pagefault[1]} - ${major_pagefault_init[1]}")
    sed -i '/pagefault/d' $file_path
    echo pagefault=$pagefault >> $file_path
    echo major_pagefault=$major_pagefault >> $file_path
}

function utils_get_container_id() {
    local name=$1
    id=$(docker inspect -f '{{.Id}}' $name)
    echo $id
}

function utils_get_container_pid() {
    local name=$1
    pid=$(docker inspect -f '{{.State.Pid}}' $name)
    echo $pid
}

function mount_tmpfs() {
    mkdir -p $TMP_FOR_MEASURE
    sudo mount -t tmpfs -o size=100M tmpfs $TMP_FOR_MEASURE
}

function init() {
    mount_tmpfs
    docker rm -f $(docker ps -a | grep "grpc_server\|grpc_app_\|grpc_exp_server\|grpc_exp_app\|pocket\|monolithic" | awk '{print $1}') > /dev/null 2>&1
    docker network rm $NETWORK
    docker network create --driver=bridge --subnet=$SUBNETMASK $NETWORK

    # if [[ "$(ps aux | grep "pocketd" | grep "root" | wc -l)" -lt "1" ]]; then
    #     echo "pocketd does not seems to be running or running without root privileged, do you still want to run?"
    #     select yn in "Yes" "No"; do
    #         case $yn in
    #             Yes ) break;;
    #             No ) exit;;
    #         esac
    #     done
    # fi
}

function init_grpc() {
    mount_tmpfs
    docker rm -f $(docker ps -a | grep "grpc_server\|grpc_app_\|grpc_exp_server\|grpc_exp_app\|pocket\|monolithic" | awk '{print $1}') > /dev/null 2>&1
    docker network rm $NETWORK
    docker network create --driver=bridge --subnet=$SUBNETMASK $NETWORK
}

function finalize() {
    sudo bash -c "echo 1 > /proc/sys/kernel/nmi_watchdog"
    sudo rm -rf $TMP_FOR_MEASURE/*
    sudo umount $TMP_FOR_MEASURE
    sleep 3
    sudo rmdir $TMP_FOR_MEASURE
    recover_cgroup
    exit
}

# deprecated
function build_image() {
    docker rmi -f $(docker image ls | grep "grpc_exp_server\|grpc_exp_client" | awk '{print $1}')

    cp ../../yolov3.weights ./dockerfiles
    docker image build --no-cache -t grpc_exp_client -f dockerfiles/Dockerfile.idapp dockerfiles
    docker image build --no-cache -t grpc_exp_server -f dockerfiles/Dockerfile.idser dockerfiles

    # docker rmi -f grpc_exp_client
    # docker image build --no-cache -t grpc_exp_client -f dockerfiles/Dockerfile.shmem.idapp dockerfiles
}

function build_shmem() {
    # docker rmi -f $(docker image ls | grep "grpc_exp_shmem_server\|grpc_exp_shmem_client" | awk '{print $1}')

    cp ../../yolov3.weights ./dockerfiles
    docker rmi -f yolo-monolithic-warm 
    docker image build --no-cache -t grpc_exp_shmem_client -f dockerfiles/Dockerfile.shmem.idapp dockerfiles
    docker image build --no-cache -t grpc_exp_shmem_client_perf -f dockerfiles/Dockerfile.shmem.perf.idapp dockerfiles
    docker image build --no-cache -t grpc_exp_shmem_server -f dockerfiles/Dockerfile.shmem.idser dockerfiles
    docker image build --no-cache -t yolo-monolithic -f dockerfiles/Dockerfile.yolo.monolithic dockerfiles
    docker image build --no-cache -t yolo-monolithic-warm -f dockerfiles/Dockerfile.yolo.monolithic dockerfiles
    docker image build --no-cache -t yolo-monolithic-perf -f dockerfiles/Dockerfile.yolo.perf.monolithic dockerfiles
}

function measure_latency_monolithic() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-latency-monolithic)
    local rusage_logging_file=tmp-service.log

    mkdir -p ${rusage_logging_dir}
    init

    # 512mb, oom
    # 512 + 256 = 768mb, oom
    # 1024mb, ok
    # 1024 + 256 = 1280mb
    # 1024 + 512 = 1536mb
    # 1024 + 1024 = 2048mb
    util_logging_latency_start yolo-monolithic-0000
    docker \
        run \
            --name yolo-monolithic-0000 \
            --memory=1024mb \
            --cpus=1.2 \
            --volume=$(pwd)/../yolov3-tf2-mono:/root/yolov3-tf2 \
            --workdir='/root/yolov3-tf2' \
            yolo-monolithic \
            python3.6 detect.py path --image data/street.jpg

    running_time=$(util_get_running_time yolo-monolithic-0000)
    echo $running_time > "${rusage_logging_dir}"/yolo-monolithic-0000.latency

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=yolo-monolithic-${index}

        util_logging_latency_start $container_name
        docker \
            run \
                -d \
                --name=${container_name} \
                --memory=1gb \
                --cpus=1.2 \
                --volume=$(pwd)/../yolov3-tf2-mono:/root/yolov3-tf2 \
                --workdir='/root/yolov3-tf2' \
                yolo-monolithic \
                python3.6 detect.py path --image data/street.jpg
        sleep $(generate_rand_num 3)
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=yolo-monolithic-${index}

        docker wait "${container_name}"
        running_time=$(util_get_running_time "${container_name}")
        echo $running_time > "${rusage_logging_dir}"/"${container_name}".latency
        echo $running_time
    done

    local folder=$(realpath data/${TIMESTAMP}-${numinstances}-graph-monolithic)
    mkdir -p $folder
    for i in $(seq 0 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=yolo-monolithic-${index}
        docker logs $container_name 2>&1 | grep "graph_construction_time" > $folder/$container_name.graph
    done

    folder=$(realpath data/${TIMESTAMP}-${numinstances}-inf-monolithic)
    mkdir -p $folder
    for i in $(seq 0 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=yolo-monolithic-${index}
        docker logs $container_name 2>&1 | grep "inference_time" > $folder/$container_name.inf
    done

    # For debugging
    docker logs -f yolo-monolithic-$(printf "%04d" $numinstances)
}

function measure_thruput_monolithic() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-latency-monolithic)
    local rusage_logging_file=tmp-service.log

    init

    # 512mb, oom
    # 512 + 256 = 768mb, oom
    # 1024mb, ok
    # 1024 + 256 = 1280mb
    # 1024 + 512 = 1536mb
    # 1024 + 1024 = 2048mb
    
    # for i in $(seq 1 $numinstances); do
    # local time_consumed=$(docker \
    #     run \
    #         --name yolo-monolithic-0000 \
    #         --memory=1024mb \
    #         --cpus=1.2 \
    #         --volume=$(pwd)/../yolov3-tf2-mono:/root/yolov3-tf2 \
    #         --workdir='/root/yolov3-tf2' \
    #         yolo-monolithic \
    #         python3.6 detect-loop.py path --image data/street.jpg --fps ${FPS} 2>&1 \
    # | grep time_consumed  | awk '{ print $6 }')
    # echo $time_consumed

    local start=$(date +%s.%N)
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=yolo-monolithic-${index}

        docker \
            run \
            -d \
            --name ${container_name} \
            --memory=1024mb \
            --cpus=1.2 \
            --volume=$(pwd)/../yolov3-tf2-mono:/root/yolov3-tf2 \
            --workdir='/root/yolov3-tf2' \
            yolo-monolithic \
            python3.6 detect-loop-infinite.py path --image data/street.jpg --fps ${FPS} > /dev/null 2>&1
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=yolo-monolithic-${index}
        docker logs ${container_name} 2>&1 | grep time_consumed | awk '{ print $6 }'
    done
    # For debugging
    # docker logs -f yolo-monolithic-$(printf "%04d" $numinstances)
}


function measure_thruput() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-latency)
    local rusage_logging_file=tmp-service.log

    local server_container_name=pocket-server-001
    local server_image=grpc_exp_shmem_server


    init
    _run_d_server_shmem_rlimit ${server_image} ${server_container_name} $NETWORK 15
    local backend_uid=$(utils_get_container_id ${server_container_name})

    # ./pocket/pocket \
    #     run \
    #         -d \
    #         -b grpc_exp_shmem_client \
    #         -t pocket-client-0000 \
    #         -s ${server_container_name} \
    #         --memory=768mb \
    #         --cpus=1 \
    #         --volume=$(pwd)/data:/data \
    #         --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
    #         --volume=$(pwd)/../yolov3-tf2/images:/img \
    #         --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
    #         --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
    #         --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
    #         --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
    #         --env CONTAINER_ID=pocket-client-0000 \
    #         --workdir='/root/yolov3-tf2' \
    #         -- python3.6 detect-loop.py --object path --image data/street.jpg --fps $FPS
    # sleep 3
    # docker wait "pocket-client-0000"
    # time_consumed=$(docker logs pocket-client-0000 2>&1 | grep time_consumed  | awk '{ print $6 }')
    # echo $time_consumed


    local start=$(date +%s.%N)
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ./pocket/pocket \
            run \
                -d \
                -b grpc_exp_shmem_client \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=768mb \
                --cpus=1 \
                --volume=$(pwd)/data:/data \
                --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=$(pwd)/../yolov3-tf2/images:/img \
                --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
                --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env CONTAINER_ID=${container_name} \
                --env BACKEND_UID=${backend_uid} \
                --workdir='/root/yolov3-tf2' \
                -- python3.6 detect-loop.py --object path --image data/street.jpg
        interval=$(generate_rand_num 3)
        docker wait $container_name
    done
    sleep 5

    # wait
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker wait "${container_name}"
    done
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker logs ${container_name} 2>&1 | grep time_consumed | awk '{ print $6 }'
    done

    # local folder=$(realpath data/${TIMESTAMP}-${numinstances}-graph)
    # mkdir -p $folder
    # for i in $(seq 0 $numinstances); do
    #     local index=$(printf "%04d" $i)
    #     local container_name=pocket-client-${index}
    #     docker logs $container_name 2>&1 | grep "graph_construction_time" > $folder/$container_name.graph
    # done

    # folder=$(realpath data/${TIMESTAMP}-${numinstances}-inf)
    # mkdir -p $folder
    # for i in $(seq 0 $numinstances); do
    #     local index=$(printf "%04d" $i)
    #     local container_name=pocket-client-${index}
    #     docker logs $container_name 2>&1 | grep "inference_time" > $folder/$container_name.inf
    # done

    # For debugging
    # docker logs pocket-server-001
    # docker logs -f pocket-client-$(printf "%04d" $numinstances)
}

function measure_latency() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-latency)
    local rusage_logging_file=tmp-service.log

    local server_container_name=pocket-server-001
    local server_image=grpc_exp_shmem_server

    mkdir -p ${rusage_logging_dir}
    init
    _run_d_server_shmem_rlimit ${server_image} ${server_container_name} $NETWORK 15
    local backend_uid=$(utils_get_container_id ${server_container_name})

    ./pocket/pocket \
        run \
            --measure-latency $rusage_logging_dir \
            -d \
            -b grpc_exp_shmem_client \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=768mb \
            --cpus=1 \
            --volume=$(pwd)/data:/data \
            --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=$(pwd)/../yolov3-tf2/images:/img \
            --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
            --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env CONTAINER_ID=pocket-client-0000 \
            --env BACKEND_UID=${backend_uid} \
            --workdir='/root/yolov3-tf2' \
            -- python3.6 detect.py --object path --image data/street.jpg

    sleep 5

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ./pocket/pocket \
            run \
                --measure-latency $rusage_logging_dir \
                -d \
                -b grpc_exp_shmem_client \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=768mb \
                --cpus=1 \
                --volume=$(pwd)/data:/data \
                --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=$(pwd)/../yolov3-tf2/images:/img \
                --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
                --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env CONTAINER_ID=${container_name} \
                --env BACKEND_UID=${backend_uid} \
                --workdir='/root/yolov3-tf2' \
                -- python3.6 detect.py --object path --image data/street.jpg &
        interval=$(generate_rand_num 3)
        echo interval $interval
        sleep $interval
    done

    wait
        # wait
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker wait "${container_name}"
    done

    local folder=$(realpath data/${TIMESTAMP}-${numinstances}-graph)
    mkdir -p $folder
    for i in $(seq 0 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker logs $container_name 2>&1 | grep "graph_construction_time" > $folder/$container_name.graph
    done

    folder=$(realpath data/${TIMESTAMP}-${numinstances}-inf)
    mkdir -p $folder
    for i in $(seq 0 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker logs $container_name 2>&1 | grep "inference_time" > $folder/$container_name.inf
    done


    folder=$(realpath data/${TIMESTAMP}-${numinstances}-rrealloc)
    mkdir -p $folder
    for i in $(seq 0 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker logs $container_name 2>&1 | grep "resource_realloc_time" > $folder/$container_name.inf
    done


    # For debugging
    docker logs pocket-server-001
    docker logs -f pocket-client-$(printf "%04d" $numinstances)
}

# measure tight resource
function measure_latency2() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-latency)
    local rusage_logging_file=tmp-service.log

    local server_container_name=pocket-server-001
    local server_image=grpc_exp_shmem_server

    mkdir -p ${rusage_logging_dir}
    init
    _run_d_server_shmem_rlimit ${server_image} ${server_container_name} $NETWORK 15
    local backend_uid=$(utils_get_container_id ${server_container_name})

    ./pocket/pocket \
        run \
            --measure-latency $rusage_logging_dir \
            -d \
            -b grpc_exp_shmem_client \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=512mb \
            --cpus=1 \
            --volume=$(pwd)/data:/data \
            --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=$(pwd)/../yolov3-tf2/images:/img \
            --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
            --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env CONTAINER_ID=pocket-client-0000 \
            --env BACKEND_UID=${backend_uid} \
            --workdir='/root/yolov3-tf2' \
            -- python3.6 detect.py --object path --image data/street.jpg

    sleep 5

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ./pocket/pocket \
            run \
                --measure-latency $rusage_logging_dir \
                -d \
                -b grpc_exp_shmem_client \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=256mb \
                --cpus=1 \
                --volume=$(pwd)/data:/data \
                --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=$(pwd)/../yolov3-tf2/images:/img \
                --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
                --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env CONTAINER_ID=${container_name} \
                --env BACKEND_UID=${backend_uid} \
                --workdir='/root/yolov3-tf2' \
                -- python3.6 detect.py --object path --image data/street.jpg &
        interval=$(generate_rand_num 3)
        echo interval $interval
        sleep $interval
    done

    wait
        # wait
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker wait "${container_name}"
    done

    # local folder=$(realpath data/${TIMESTAMP}-${numinstances}-graph)
    # mkdir -p $folder
    # for i in $(seq 0 $numinstances); do
    #     local index=$(printf "%04d" $i)
    #     local container_name=pocket-client-${index}
    #     docker logs $container_name 2>&1 | grep "graph_construction_time" > $folder/$container_name.graph
    # done

    # folder=$(realpath data/${TIMESTAMP}-${numinstances}-inf)
    # mkdir -p $folder
    # for i in $(seq 0 $numinstances); do
    #     local index=$(printf "%04d" $i)
    #     local container_name=pocket-client-${index}
    #     docker logs $container_name 2>&1 | grep "inference_time" > $folder/$container_name.inf
    # done


    # folder=$(realpath data/${TIMESTAMP}-${numinstances}-rrealloc)
    # mkdir -p $folder
    # for i in $(seq 0 $numinstances); do
    #     local index=$(printf "%04d" $i)
    #     local container_name=pocket-client-${index}
    #     docker logs $container_name 2>&1 | grep "resource_realloc_time" > $folder/$container_name.inf
    # done

    folder=$(realpath data/${TIMESTAMP}-${numinstances}-inf)
    mkdir -p $folder
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker logs $container_name 2>&1 | grep "inference_time"
    done

}


function measure_inf_thruput() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-latency)
    local rusage_logging_file=tmp-service.log

    local server_container_name=pocket-server-001
    local server_image=grpc_exp_shmem_server

    mkdir -p ${rusage_logging_dir}
    init
    _run_d_server_shmem_rlimit ${server_image} ${server_container_name} $NETWORK 15
    local backend_uid=$(utils_get_container_id ${server_container_name})

    ./pocket/pocket \
        run \
            -d \
            -b grpc_exp_shmem_client \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=768mb \
            --cpus=1 \
            --volume=$(pwd)/data:/data \
            --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=$(pwd)/../yolov3-tf2/images:/img \
            --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
            --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
            --volume=/sys/fs/cgroup:/ext/cg \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env CONTAINER_ID=pocket-client-0000 \
            --env BACKEND_UID=${backend_uid} \
            --workdir='/root/yolov3-tf2' \
            -- python3.6 detect.py --object path --image data/street.jpg

    sleep 5

    # for i in $(seq 1 $(echo $numinstances - 1 | bc)); do
    # for i in $(seq 1 $(echo "$numinstances - 1" | bc)); do
    for i in $(seq 1 $(echo "$numinstances-1" | bc)); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ./pocket/pocket \
            run \
                -d \
                -b grpc_exp_shmem_client \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=768mb \
                --cpus=1 \
                --volume=$(pwd)/data:/data \
                --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=$(pwd)/../yolov3-tf2/images:/img \
                --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
                --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
                --volume=/sys/fs/cgroup:/ext/cg \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env CONTAINER_ID=${container_name} \
                --env BACKEND_UID=${backend_uid} \
                --workdir='/root/yolov3-tf2' \
                -- python3.6 zombie.py --object path --image data/street.jpg &
        interval=$(generate_rand_num 3)
        echo interval $interval
        sleep $interval
    done

    sleep 6

    index=$(printf "%04d" $numinstances)
    container_name=pocket-client-${index}
    for i in $(seq 1 10); do
        ./pocket/pocket \
            run \
                -d \
                -b grpc_exp_shmem_client \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=768mb \
                --cpus=1 \
                --volume=$(pwd)/data:/data \
                --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=$(pwd)/../yolov3-tf2/images:/img \
                --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
                --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
                --volume=/sys/fs/cgroup:/ext/cg \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env CONTAINER_ID=${container_name} \
                --env BACKEND_UID=${backend_uid} \
                --workdir='/root/yolov3-tf2' \
                -- python3.6 detect-per-inf.py --object path --image data/street.jpg &
        sleep 3
        docker wait "${container_name}"
        docker logs ${container_name} 2>&1 | grep 'fe_cpu_time'
        docker logs ${container_name} 2>&1 | grep 'be_cpu_time'
        docker rm -f ${container_name}
        sleep 5
    done

    # For debugging
    # docker logs -f pocket-client-$(printf "%04d" $numinstances)
    # docker logs -f pocket-client-$(printf "%04d" $(echo "$numinstances-1" | bc))
}

function measure_inf_thruput_monolithic() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-latency)
    local rusage_logging_file=tmp-service.log

    local server_container_name=pocket-server-001
    local server_image=grpc_exp_shmem_server

    mkdir -p ${rusage_logging_dir}
    init

    docker \
        run \
            --name yolo-monolithic-0000 \
            --memory=1024mb \
            --cpus=1.2 \
            --volume=$(pwd)/../yolov3-tf2-mono:/root/yolov3-tf2 \
            --workdir='/root/yolov3-tf2' \
            yolo-monolithic \
            python3.6 detect.py path --image data/street.jpg > /dev/null 2>&1


    sleep 5

    # for i in $(seq 1 $(echo $numinstances - 1 | bc)); do
    # for i in $(seq 1 $(echo "$numinstances - 1" | bc)); do
    for i in $(seq 1 $(echo "$numinstances-1" | bc)); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        docker \
            run \
                -d \
                --name=${container_name} \
                --memory=1gb \
                --cpus=1.2 \
                --volume=$(pwd)/../yolov3-tf2-mono:/root/yolov3-tf2 \
                --workdir='/root/yolov3-tf2' \
                yolo-monolithic \
                python3.6 zombie.py path --image data/street.jpg
        sleep $(generate_rand_num 3)
        interval=$(generate_rand_num 3)
        echo interval $interval
        sleep $interval
    done

    sleep 6

    index=$(printf "%04d" $numinstances)
    container_name=pocket-client-${index}
    for i in $(seq 1 10); do
        docker \
            run \
                -d \
                --name=${container_name} \
                --memory=1gb \
                --cpus=1.2 \
                --volume=$(pwd)/../yolov3-tf2-mono:/root/yolov3-tf2 \
                --workdir='/root/yolov3-tf2' \
                yolo-monolithic \
                python3.6 detect-per-inf.py path --image data/street.jpg
        sleep 3

        docker wait "${container_name}"
        # echo ============
        docker logs ${container_name} 2>&1 | grep 'fe_cpu_time'
        docker rm -f ${container_name}
        sleep 5
    done
    # docker logs ${container_name} 2>&1 | grep 'be_cpu_time'
    # echo ============

    # For debugging
    # docker logs -f ${container_name}
    # docker logs -f pocket-client-$(printf "%04d" $(echo "$numinstances-1" | bc))
}

function measure_latency_grpc() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-latency)
    local rusage_logging_file=tmp-service.log

    local server_container_name=pocket-server-001
    local server_image=grpc_exp_shmem_server

    mkdir -p ${rusage_logging_dir}
    init_grpc
    _run_d_server_grpc_rlimit ${server_image} ${server_container_name} $NETWORK 15
    local backend_uid=$(utils_get_container_id ${server_container_name})

    ./pocket/pocket \
        run \
            --measure-latency $rusage_logging_dir \
            --no-ipc \
            -d \
            -b grpc_exp_shmem_client \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=768mb \
            --cpus=1 \
            --network=$NETWORK \
            --volume=$(pwd)/data:/data \
            --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=$(pwd)/../yolov3-tf2-grpc/images:/img \
            --volume=$(pwd)/../yolov3-tf2-grpc:/root/yolov3-tf2 \
            --volume=$(pwd)/../tfrpc/client-grpc:/root/tfrpc/client \
            --env SERVER_ADDR=${SERVER_IP} \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env CONTAINER_ID=pocket-client-0000 \
            --env BACKEND_UID=${backend_uid} \
            --workdir='/root/yolov3-tf2' \
            -- python3.6 detect.py --object path --image data/street.jpg

    sleep 5

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ./pocket/pocket \
            run \
                --measure-latency $rusage_logging_dir \
                --no-ipc \
                -d \
                -b grpc_exp_shmem_client \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=768mb \
                --cpus=1 \
                --volume=$(pwd)/data:/data \
                --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=$(pwd)/../yolov3-tf2-grpc/images:/img \
                --volume=$(pwd)/../yolov3-tf2-grpc:/root/yolov3-tf2 \
                --volume=$(pwd)/../tfrpc/client-grpc:/root/tfrpc/client \
                --network=$NETWORK \
                --env SERVER_ADDR=${SERVER_IP} \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env CONTAINER_ID=${container_name} \
                --env BACKEND_UID=${backend_uid} \
                --workdir='/root/yolov3-tf2' \
                -- python3.6 detect.py --object path --image data/street.jpg &
        interval=$(generate_rand_num 3)
        echo interval $interval
        sleep $interval
    done

    wait

    local folder=$(realpath data/${TIMESTAMP}-${numinstances}-graph)
    mkdir -p $folder
    for i in $(seq 0 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker logs $container_name 2>&1 | grep "graph_construction_time" > $folder/$container_name.graph
    done

    folder=$(realpath data/${TIMESTAMP}-${numinstances}-inf)
    mkdir -p $folder
    for i in $(seq 0 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker logs $container_name 2>&1 | grep "inference_time" > $folder/$container_name.inf
    done

    # For debugging
    docker logs pocket-server-001
    docker logs -f pocket-client-$(printf "%04d" $numinstances)
}

function measure_rusage_monolithic() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-rusage-monolithic)
    local rusage_logging_file=tmp-service.log

    mkdir -p ${rusage_logging_dir}
    init


    # 512mb, oom
    # 512 + 256 = 768mb, oom
    # 1024mb, ok
    # 1024 + 256 = 1280mb
    # 1024 + 512 = 1536mb
    # 1024 + 1024 = 2048mb
    docker \
        run \
            -di \
            --name yolo-monolithic-0000 \
            --memory=1024mb \
            --cpus=1.2 \
            --volume=$(pwd)/../yolov3-tf2-mono:/root/yolov3-tf2 \
            --workdir='/root/yolov3-tf2' \
            yolo-monolithic \
            bash

    docker \
        exec \
            yolo-monolithic-0000 \
            python3.6 detect.py path --image data/street.jpg

    ./pocket/pocket \
        rusage \
        measure yolo-monolithic-0000 --dir ${rusage_logging_dir} 

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=yolo-monolithic-${index}

        docker \
            run \
                -di \
                --name=${container_name} \
                --memory=1gb \
                --cpus=1.2 \
                --volume=$(pwd)/../yolov3-tf2-mono:/root/yolov3-tf2 \
                --workdir='/root/yolov3-tf2' \
                yolo-monolithic \
                bash
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=yolo-monolithic-${index}

        docker \
            exec \
                ${container_name} \
                python3.6 detect.py path --image data/street.jpg &
        sleep $(generate_rand_num 3)
    done

    wait

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=yolo-monolithic-${index}

        ./pocket/pocket \
            rusage \
            measure ${container_name} --dir ${rusage_logging_dir} 
    done

    # For debugging
    # docker logs -f yolo-monolithic-$(printf "%04d" $numinstances)
}

function measure_perf_monolithic() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-perf-monolithic)
    local rusage_logging_file=tmp-service.log

    mkdir -p ${rusage_logging_dir}
    init


    # 512mb, oom
    # 512 + 256 = 768mb, oom
    # 1024mb, ok
    # 1024 + 256 = 1280mb
    # 1024 + 512 = 1536mb
    # 1024 + 1024 = 2048mb
    docker \
        run \
            -d \
            --name yolo-monolithic-0000 \
            --memory=1024mb \
            --cpus=1.2 \
            --workdir='/root/yolov3-tf2' \
            --cap-add SYS_ADMIN \
            --cap-add IPC_LOCK \
            --volume=$(pwd)/data:/data \
            yolo-monolithic-perf \
            perf stat -e $PERF_COUNTERS -o /data/$TIMESTAMP-${numinstances}-perf-monolithic/yolo-monolithic-0000.perf.log python3.6 detect.py path --image data/street.jpg

    docker \
        wait \
            yolo-monolithic-0000


    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=yolo-monolithic-${index}

        docker \
            run \
                -d \
                --name=${container_name} \
                --memory=1gb \
                --cpus=1.2 \
                --workdir='/root/yolov3-tf2' \
                --cap-add SYS_ADMIN \
                --cap-add IPC_LOCK \
                --volume=$(pwd)/data:/data \
                yolo-monolithic-perf \
                perf stat -e $PERF_COUNTERS -o /data/$TIMESTAMP-${numinstances}-perf-monolithic/${container_name}.perf.log python3.6 detect.py path --image data/street.jpg
        sleep $(generate_rand_num 3)
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=yolo-monolithic-${index}

        docker \
            wait \
                ${container_name}        
    done


    # For debugging
    # docker logs -f yolo-monolithic-$(printf "%04d" $numinstances)
}

function measure_latency_monolithic_warm() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-latency-monolithic)
    local rusage_logging_file=tmp-service.log

    # mkdir -p ${rusage_logging_dir}
    init


    # 512mb, oom
    # 512 + 256 = 768mb, oom
    # 1024mb, ok
    # 1024 + 256 = 1280mb
    # 1024 + 512 = 1536mb
    # 1024 + 1024 = 2048mb
    # docker \
    #     run \
    #         --name yolo-monolithic-0000 \
    #         --memory=1024mb \
    #         --cpus=1.2 \
    #         --workdir='/root/yolov3-tf2' \
    #         yolo-monolithic-warm \
    #         python3.6 detect.py path --image data/street.jpg

    # running_time=$(util_get_running_time yolo-monolithic-0000)
    # echo $running_time > "${rusage_logging_dir}"/yolo-monolithic-0000.latency

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=yolo-monolithic-${index}

        util_logging_latency_start $container_name
        docker \
            run \
                -d \
                --name=${container_name} \
                --memory=1gb \
                --cpus=1.2 \
                --workdir='/root/yolov3-tf2' \
                yolo-monolithic-warm \
                python3.6 detect.py path --image data/street.jpg
        sleep $(generate_rand_num 3)
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=yolo-monolithic-${index}

        docker wait "${container_name}"
        running_time=$(util_get_running_time "${container_name}")
        # echo $running_time > "${rusage_logging_dir}"/"${container_name}".latency
        echo $running_time
    done

    # local folder=$(realpath data/${TIMESTAMP}-${numinstances}-graph-monolithic)
    # mkdir -p $folder
    for i in $(seq 0 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=yolo-monolithic-${index}
        docker logs $container_name 2>&1 | grep "time"
        # docker logs $container_name 2>&1 | grep "graph_construction_time" > $folder/$container_name.graph
    done

    # folder=$(realpath data/${TIMESTAMP}-${numinstances}-inf-monolithic)
    # mkdir -p $folder
    # for i in $(seq 1 $numinstances); do
    #     local index=$(printf "%04d" $i)
    #     local container_name=yolo-monolithic-${index}
    #     docker logs $container_name 2>&1 | grep "inference_time" > $folder/$container_name.inf
    # done

    # For debugging
    # docker logs -f yolo-monolithic-$(printf "%04d" $numinstances)
}


# function measure_perf_monolithic() {
#     local numinstances=$1
#     local container_list=()
#     local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-perf)
#     local rusage_logging_file=tmp-service.log

#     local server_container_name=pocket-server-001
#     local server_image=grpc_exp_shmem_server

#     mkdir -p ${rusage_logging_dir}
#     init
#     sudo bash -c "echo 0 > /proc/sys/kernel/nmi_watchdog"

#     # sudo python unix_multi_server.py &
#     _run_d_server_shmem_rlimit_perf ${server_image} ${server_container_name} $NETWORK $TIMESTAMP 15

#     docker \
#         run \
#             -d \
#             --name=yolo-monolithic-0000 \
#             --memory=1gb \
#             --cpus=1.2 \
#             --workdir='/root/yolov3-tf2' \
#             --cap-add SYS_ADMIN \
#             --cap-add IPC_LOCK \
#             --volume=$(pwd)/../yolov3-tf2-mono:/root/yolov3-tf2 \
#             --volume=$(pwd)/data:/data \
#             yolo-monolithic-perf \
#             perf stat -e $PERF_COUNTERS -o /data/$TIMESTAMP-${numinstances}-perf-monolithic/yolo-monolithic-0000.perf.log python3.6 detect.py path --image data/street.jpg
#     sleep $(generate_rand_num 3)
#     docker \
#         wait \
#             yolo-monolithic-0000


#     for i in $(seq 1 $numinstances); do
#         local index=$(printf "%04d" $i)
#         local container_name=yolo-monolithic-${index}

#         docker \
#             run \
#                 -d \
#                 --name=${container_name} \
#                 --memory=1gb \
#                 --cpus=1.2 \
#                 --workdir='/root/yolov3-tf2' \
#                 --cap-add SYS_ADMIN \
#                 --cap-add IPC_LOCK \
#                 --volume=$(pwd)/../yolov3-tf2-mono:/root/yolov3-tf2 \
#                 --volume=$(pwd)/data:/data \
#                 yolo-monolithic-perf \
#                 perf stat -e $PERF_COUNTERS -o /data/$TIMESTAMP-${numinstances}-perf-monolithic/${container_name}.perf.log python3.6 detect.py path --image data/street.jpg
#         sleep $(generate_rand_num 3)
#     done

#     for i in $(seq 1 $numinstances); do
#         local index=$(printf "%04d" $i)
#         local container_name=yolo-monolithic-${index}

#         docker \
#             wait \
#                 ${container_name}        
#     done


#     # For debugging
#     # docker logs -f yolo-monolithic-$(printf "%04d" $numinstances)
# }


function measure_energy_monolithic() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-perf-monolithic)
    local rusage_logging_file=tmp-service.log

    mkdir -p ${rusage_logging_dir}
    init


    # 512mb, oom
    # 512 + 256 = 768mb, oom
    # 1024mb, ok
    # 1024 + 256 = 1280mb
    # 1024 + 512 = 1536mb
    # 1024 + 1024 = 2048mb
    docker \
        run \
            -d \
            --name yolo-monolithic-0000 \
            --memory=1024mb \
            --cpus=1.2 \
            --workdir='/root/yolov3-tf2' \
            --cap-add SYS_ADMIN \
            --cap-add IPC_LOCK \
            --volume=$(pwd)/../yolov3-tf2-mono:/root/yolov3-tf2 \
            --volume=$(pwd)/data:/data \
            yolo-monolithic-perf \
            perf stat -a -e power/energy-pkg/,power/energy-ram/ -o /data/$TIMESTAMP-${numinstances}-energy-monolithic/yolo-monolithic-0000.perf.log python3.6 detect.py path --image data/street.jpg

    docker \
        wait \
            yolo-monolithic-0000


    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=yolo-monolithic-${index}

        docker \
            run \
                -d \
                --name=${container_name} \
                --memory=1gb \
                --cpus=1.2 \
                --workdir='/root/yolov3-tf2' \
                --cap-add SYS_ADMIN \
                --cap-add IPC_LOCK \
                --volume=$(pwd)/../yolov3-tf2-mono:/root/yolov3-tf2 \
                --volume=$(pwd)/data:/data \
                yolo-monolithic-perf \
                perf stat -a -e power/energy-pkg/,power/energy-ram/ -o /data/$TIMESTAMP-${numinstances}-energy-monolithic/${container_name}.perf.log python3.6 detect.py path --image data/street.jpg
        sleep $(generate_rand_num 3)
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=yolo-monolithic-${index}

        docker \
            wait \
                ${container_name}        
    done


    # For debugging
    # docker logs -f yolo-monolithic-$(printf "%04d" $numinstances)
}

function measure_rusage() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-rusage)
    local rusage_logging_file=tmp-service.log

    local server_container_name=pocket-server-001
    local server_image=grpc_exp_shmem_server

    mkdir -p ${rusage_logging_dir}
    init
    _run_d_server_shmem_rlimit ${server_image} ${server_container_name} $NETWORK 15
    local backend_uid=$(utils_get_container_id ${server_container_name})

    ### rusage measure needs 'd' flag
    ./pocket/pocket \
        run \
            --rusage $rusage_logging_dir \
            -d \
            -b grpc_exp_shmem_client \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=768mb \
            --cpus=1 \
            --volume=$(pwd)/data:/data \
            --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=$(pwd)/../yolov3-tf2/images:/img \
            --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
            --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env CONTAINER_ID=pocket-client-0000 \
            --env BACKEND_UID=${backend_uid} \
            --workdir='/root/yolov3-tf2' \
            -- python3.6 detect.py --object path --image data/street.jpg &

    sleep 5

    ./pocket/pocket \
        wait \
        pocket-client-0000

    sleep 5

    sudo ./pocket/pocket \
        rusage \
        init ${server_container_name} --dir ${rusage_logging_dir} 

    sleep 5

    ### Firing multiple instances with rusage flag requires & at the end.
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ./pocket/pocket \
            run \
                --rusage $rusage_logging_dir \
                -d \
                -b grpc_exp_shmem_client \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=768mb \
                --cpus=1 \
                --volume=$(pwd)/data:/data \
                --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=$(pwd)/../yolov3-tf2/images:/img \
                --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
                --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env CONTAINER_ID=${container_name} \
                --env BACKEND_UID=${backend_uid} \
                --workdir='/root/yolov3-tf2' \
                -- python3.6 detect.py --object path --image data/street.jpg &
        sleep $(generate_rand_num 3)
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        # docker wait "${container_name}"
        ./pocket/pocket \
            wait \
                ${container_name}
    done

    ./pocket/pocket \
        rusage \
        measure ${server_container_name} --dir ${rusage_logging_dir} 
}


function measure_rusage_grpc() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-rusage)
    local rusage_logging_file=tmp-service.log

    local server_container_name=pocket-server-001
    local server_image=grpc_exp_shmem_server

    mkdir -p ${rusage_logging_dir}
    init_grpc
    _run_d_server_grpc_rlimit ${server_image} ${server_container_name} $NETWORK 15
    local backend_uid=$(utils_get_container_id ${server_container_name})

    ### rusage measure needs 'd' flag
    ./pocket/pocket \
        run \
            --rusage $rusage_logging_dir \
            --no-ipc \
            -d \
            -b grpc_exp_shmem_client \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=768mb \
            --cpus=1 \
            --volume=$(pwd)/data:/data \
            --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=$(pwd)/../yolov3-tf2-grpc/images:/img \
            --volume=$(pwd)/../yolov3-tf2-grpc:/root/yolov3-tf2 \
            --volume=$(pwd)/../tfrpc/client-grpc:/root/tfrpc/client \
            --network=$NETWORK \
            --env SERVER_ADDR=${SERVER_IP} \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env CONTAINER_ID=pocket-client-0000 \
            --env BACKEND_UID=${backend_uid} \
            --workdir='/root/yolov3-tf2' \
            -- python3.6 detect.py --object path --image data/street.jpg &

    sleep 2
    echo attach to client
    docker attach pocket-client-0000
    docker logs pocket-client-0000

    echo ==
    echo

    ./pocket/pocket \
        wait \
        pocket-client-0000

    sleep 5

    sudo ./pocket/pocket \
        rusage \
        init ${server_container_name} --dir ${rusage_logging_dir} 

    sleep 5

    ### Firing multiple instances with rusage flag requires & at the end.
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ./pocket/pocket \
            run \
                --rusage $rusage_logging_dir \
                --no-ipc \
                -d \
                -b grpc_exp_shmem_client \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=768mb \
                --cpus=1 \
                --volume=$(pwd)/data:/data \
                --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=$(pwd)/../yolov3-tf2-grpc/images:/img \
                --volume=$(pwd)/../yolov3-tf2-grpc:/root/yolov3-tf2 \
                --volume=$(pwd)/../tfrpc/client-grpc:/root/tfrpc/client \
                --network=$NETWORK \
                --env SERVER_ADDR=${SERVER_IP} \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env CONTAINER_ID=${container_name} \
                --env BACKEND_UID=${backend_uid} \
                --workdir='/root/yolov3-tf2' \
                -- python3.6 detect.py --object path --image data/street.jpg &
        sleep $(generate_rand_num 3)
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        # docker wait "${container_name}"
        ./pocket/pocket \
            wait \
                ${container_name}
    done

    ./pocket/pocket \
        rusage \
        measure ${server_container_name} --dir ${rusage_logging_dir} 
}

function measure_cprofile() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-cprofile)
    local rusage_logging_file=tmp-service.log

    local server_container_name=pocket-server-001
    local server_image=grpc_exp_shmem_server

    mkdir -p ${rusage_logging_dir}
    init
    _run_d_server_shmem_rlimit_cProfile ${server_image} ${server_container_name} $NETWORK $TIMESTAMP $numinstances 15
    local backend_uid=$(utils_get_container_id ${server_container_name})

    ./pocket/pocket \
        run \
            --cprofile $rusage_logging_dir \
            -d \
            -b grpc_exp_shmem_client \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=768mb \
            --cpus=1 \
            --volume=$(pwd)/data:/data \
            --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=$(pwd)/../yolov3-tf2/images:/img \
            --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
            --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env CONTAINER_ID=pocket-client-0000 \
            --env BACKEND_UID=${backend_uid} \
            --workdir='/root/yolov3-tf2' \
            -- python3.6 -m cProfile -o /data/${TIMESTAMP}-${numinstances}-cprofile/pocket-client-0000.cprofile detect.py --object path --image data/street.jpg
    
    sleep 5

    ./pocket/pocket \
        wait \
        pocket-client-0000

    sleep 5

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ./pocket/pocket \
            run \
                --cprofile $rusage_logging_dir \
                -d \
                -b grpc_exp_shmem_client \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=768mb \
                --cpus=1 \
                --volume=$(pwd)/data:/data \
                --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=$(pwd)/../yolov3-tf2/images:/img \
                --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
                --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env CONTAINER_ID=${container_name} \
                --env BACKEND_UID=${backend_uid} \
                --workdir='/root/yolov3-tf2' \
                -- python3.6 -m cProfile -o /data/${TIMESTAMP}-${numinstances}-cprofile/${container_name}.cprofile detect.py --object path --image data/street.jpg
        sleep $(generate_rand_num 3)
    done

    sleep 5


    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ./pocket/pocket \
            wait \
                ${container_name}
    done

    sleep 3

    ./pocket/pocket \
        service \
            kill ${server_container_name} \

    sleep 3
    sudo bash -c "echo 1 > /proc/sys/kernel/nmi_watchdog"

    for filename in data/$TIMESTAMP-${numinstances}-cprofile/* ; do
        echo $filename
        if [[ "$filename" == *.cprofile ]]; then
            ./pocket/parseprof -f "$filename"
        fi
    done

    # For debugging
    docker logs -f pocket-client-$(printf "%04d" $numinstances)
}

function measure_cprofile_grpc() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-cprofile)
    local rusage_logging_file=tmp-service.log

    local server_container_name=pocket-server-001
    local server_image=grpc_exp_shmem_server

    mkdir -p ${rusage_logging_dir}
    init
    _run_d_server_grpc_rlimit_cProfile ${server_image} ${server_container_name} $NETWORK $TIMESTAMP $numinstances 15
    local backend_uid=$(utils_get_container_id ${server_container_name})

    ./pocket/pocket \
        run \
            --cprofile $rusage_logging_dir \
            --no-ipc \
            -d \
            -b grpc_exp_shmem_client \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=768mb \
            --cpus=1 \
            --volume=$(pwd)/data:/data \
            --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=$(pwd)/../yolov3-tf2-grpc/images:/img \
            --volume=$(pwd)/../yolov3-tf2-grpc:/root/yolov3-tf2 \
            --volume=$(pwd)/../tfrpc/client-grpc:/root/tfrpc/client \
            --network=$NETWORK \
            --env SERVER_ADDR=${SERVER_IP} \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env CONTAINER_ID=pocket-client-0000 \
            --env BACKEND_UID=${backend_uid} \
            --workdir='/root/yolov3-tf2' \
            -- python3.6 -m cProfile -o /data/${TIMESTAMP}-${numinstances}-cprofile/pocket-client-0000.cprofile detect.py --object path --image data/street.jpg

    sleep 5

    ./pocket/pocket \
        wait \
        pocket-client-0000

    sleep 3

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ./pocket/pocket \
            run \
                --cprofile $rusage_logging_dir \
                -d \
                --no-ipc \
                -b grpc_exp_shmem_client \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=768mb \
                --cpus=1 \
                --volume=$(pwd)/data:/data \
                --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=$(pwd)/../yolov3-tf2-grpc/images:/img \
                --volume=$(pwd)/../yolov3-tf2-grpc:/root/yolov3-tf2 \
                --volume=$(pwd)/../tfrpc/client-grpc:/root/tfrpc/client \
                --network=$NETWORK \
                --env SERVER_ADDR=${SERVER_IP} \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env CONTAINER_ID=${container_name} \
                --env BACKEND_UID=${backend_uid} \
                --workdir='/root/yolov3-tf2' \
                -- python3.6 -m cProfile -o /data/${TIMESTAMP}-${numinstances}-cprofile/${container_name}.cprofile detect.py --object path --image data/street.jpg
        sleep $(generate_rand_num 3)
    done


    sleep 5

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ./pocket/pocket \
            wait \
                ${container_name}
    done

    sleep 3

    ./pocket/pocket \
        service \
            kill ${server_container_name} \

    sleep 3
    sudo bash -c "echo 1 > /proc/sys/kernel/nmi_watchdog"

    for filename in data/$TIMESTAMP-${numinstances}-cprofile/* ; do
        echo $filename
        if [[ "$filename" == *.cprofile ]]; then
            ./pocket/parseprof -f "$filename"
        fi
    done

    # For debugging
    docker logs -f pocket-client-$(printf "%04d" $numinstances)
}

function measure_perf() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-perf)
    local rusage_logging_file=tmp-service.log

    local server_container_name=pocket-server-001
    local server_image=grpc_exp_shmem_server

    mkdir -p ${rusage_logging_dir}
    init
    sudo bash -c "echo 0 > /proc/sys/kernel/nmi_watchdog"

    # sudo python unix_multi_server.py &
    _run_d_server_shmem_rlimit_perf ${server_image} ${server_container_name} $NETWORK $TIMESTAMP 15
    local backend_uid=$(utils_get_container_id ${server_container_name})

    ./pocket/pocket \
        run \
            --perf $rusage_logging_dir \
            -d \
            -b grpc_exp_shmem_client_perf \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=768mb \
            --cpus=1 \
            --volume=$(pwd)/data:/data \
            --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=$(pwd)/../yolov3-tf2/images:/img \
            --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
            --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env CONTAINER_ID=pocket-client-0000 \
            --env BACKEND_UID=${backend_uid} \
            --workdir='/root/yolov3-tf2' \
            -- perf stat -e $PERF_COUNTERS -o /data/$TIMESTAMP-${numinstances}-perf/pocket-client-0000.perf.log python3.6 detect.py --object path --image data/street.jpg


    sleep 5
    ./pocket/pocket \
        wait \
        pocket-client-0000

    docker ps -a

    sleep 5

    local perf_record_pid=$(sudo ./pocket/pocket \
        service \
        perf ${server_container_name} --dir ${rusage_logging_dir} --counters $PERF_COUNTERS)

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ./pocket/pocket \
            run \
                -d \
                --perf $rusage_logging_dir \
                -b grpc_exp_shmem_client_perf \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=768mb \
                --cpus=1 \
                --volume=$(pwd)/data:/data \
                --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=$(pwd)/../yolov3-tf2/images:/img \
                --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
                --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env CONTAINER_ID=$container_name \
                --env BACKEND_UID=${backend_uid} \
                --workdir='/root/yolov3-tf2' \
                -- perf stat -e $PERF_COUNTERS -o /data/$TIMESTAMP-${numinstances}-perf/$container_name.perf.log python3.6 detect.py --object path --image data/street.jpg
        sleep $(generate_rand_num 3)
    done

    sudo bash -c "echo 1 > /proc/sys/kernel/nmi_watchdog"

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ./pocket/pocket \
            wait \
                ${container_name}
    done
    sudo kill -s INT $perf_record_pid

    ./pocket/pocket \
        service \
            kill ${server_container_name} \

    sleep 3

    # For debugging
    docker logs ${server_container_name}
    docker logs -f pocket-client-$(printf "%04d" $numinstances)
}

function measure_perf_grpc() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-perf)
    local rusage_logging_file=tmp-service.log

    local server_container_name=pocket-server-001
    local server_image=grpc_exp_shmem_server

    mkdir -p ${rusage_logging_dir}
    init_grpc
    sudo bash -c "echo 0 > /proc/sys/kernel/nmi_watchdog"

    # sudo python unix_multi_server.py &
    _run_d_server_grpc_rlimit_perf ${server_image} ${server_container_name} $NETWORK $TIMESTAMP 15
    local backend_uid=$(utils_get_container_id ${server_container_name})

    ./pocket/pocket \
        run \
            --perf $rusage_logging_dir \
            --no-ipc \
            -d \
            -b grpc_exp_shmem_client_perf \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=768mb \
            --cpus=1 \
            --volume=$(pwd)/data:/data \
            --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=$(pwd)/../yolov3-tf2-grpc/images:/img \
            --volume=$(pwd)/../yolov3-tf2-grpc:/root/yolov3-tf2 \
            --volume=$(pwd)/../tfrpc/client-grpc:/root/tfrpc/client \
            --network=$NETWORK \
            --env SERVER_ADDR=${SERVER_IP} \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env CONTAINER_ID=pocket-client-0000 \
            --env BACKEND_UID=${backend_uid} \
            --workdir='/root/yolov3-tf2' \
            -- perf stat -e $PERF_COUNTERS -o /data/$TIMESTAMP-${numinstances}-perf/pocket-client-0000.perf.log python3.6 detect.py --object path --image data/street.jpg


    sleep 5
    ./pocket/pocket \
        wait \
        pocket-client-0000

    docker ps -a

    sleep 5

    local perf_record_pid=$(sudo ./pocket/pocket \
        service \
        perf ${server_container_name} --dir ${rusage_logging_dir} --counters cpu-cycles,page-faults,minor-faults,major-faults,cache-misses,LLC-load-misses,LLC-store-misses,dTLB-load-misses,iTLB-load-misses)

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ./pocket/pocket \
            run \
                -d \
                --perf $rusage_logging_dir \
                --no-ipc \
                -b grpc_exp_shmem_client_perf \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=768mb \
                --cpus=1 \
                --volume=$(pwd)/data:/data \
                --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=$(pwd)/../yolov3-tf2-grpc/images:/img \
                --volume=$(pwd)/../yolov3-tf2-grpc:/root/yolov3-tf2 \
                --volume=$(pwd)/../tfrpc/client-grpc:/root/tfrpc/client \
                --network=$NETWORK \
                --env SERVER_ADDR=${SERVER_IP} \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env CONTAINER_ID=$container_name \
                --env BACKEND_UID=${backend_uid} \
                --workdir='/root/yolov3-tf2' \
                -- perf stat -e $PERF_COUNTERS -o /data/$TIMESTAMP-${numinstances}-perf/$container_name.perf.log python3.6 detect.py --object path --image data/street.jpg
        sleep $(generate_rand_num 3)
    done

    sudo bash -c "echo 1 > /proc/sys/kernel/nmi_watchdog"

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ./pocket/pocket \
            wait \
                ${container_name}
    done
    sudo kill -s INT $perf_record_pid

    ./pocket/pocket \
        service \
            kill ${server_container_name} \

    sleep 3

    # For debugging
    docker logs ${server_container_name}
    docker logs -f pocket-client-$(printf "%04d" $numinstances)
}

function measure_energy() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-perf)
    local rusage_logging_file=tmp-service.log

    local server_container_name=pocket-server-001
    local server_image=grpc_exp_shmem_server

    mkdir -p ${rusage_logging_dir}
    init
    sudo bash -c "echo 0 > /proc/sys/kernel/nmi_watchdog"

    # sudo python unix_multi_server.py &
    _run_d_server_shmem_rlimit_perf ${server_image} ${server_container_name} $NETWORK $TIMESTAMP 15
    local backend_uid=$(utils_get_container_id ${server_container_name})

    ./pocket/pocket \
        run \
            --perf $rusage_logging_dir \
            -d \
            -b grpc_exp_shmem_client_perf \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=768mb \
            --cpus=1 \
            --volume=$(pwd)/data:/data \
            --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=$(pwd)/../yolov3-tf2/images:/img \
            --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
            --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env CONTAINER_ID=pocket-client-0000 \
            --env BACKEND_UID=${backend_uid} \
            --workdir='/root/yolov3-tf2' \
            -- perf stat -a -e power/energy-pkg/,power/energy-ram/ -o /data/$TIMESTAMP-${numinstances}-energy/pocket-client-0000.perf.log python3.6 detect.py --object path --image data/street.jpg


    sleep 5
    ./pocket/pocket \
        wait \
        pocket-client-0000

    docker ps -a

    sleep 5

    local perf_record_pid=$(sudo ./pocket/pocket \
        service \
        perf ${server_container_name} --dir ${rusage_logging_dir} --counters $PERF_COUNTERS)

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ./pocket/pocket \
            run \
                -d \
                --perf $rusage_logging_dir \
                -b grpc_exp_shmem_client_perf \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=768mb \
                --cpus=1 \
                --volume=$(pwd)/data:/data \
                --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=$(pwd)/../yolov3-tf2/images:/img \
                --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
                --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env CONTAINER_ID=$container_name \
                --env BACKEND_UID=${backend_uid} \
                --workdir='/root/yolov3-tf2' \
                -- perf stat -a -e power/energy-pkg/,power/energy-ram/ -o /data/$TIMESTAMP-${numinstances}-energy/$container_name.perf.log python3.6 detect.py --object path --image data/street.jpg
        sleep $(generate_rand_num 3)
    done

    sudo bash -c "echo 1 > /proc/sys/kernel/nmi_watchdog"

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ./pocket/pocket \
            wait \
                ${container_name}
    done
    sudo kill -s INT $perf_record_pid

    ./pocket/pocket \
        service \
            kill ${server_container_name} \

    sleep 3

    # For debugging
    docker logs ${server_container_name}
    docker logs -f pocket-client-$(printf "%04d" $numinstances)
}

function measure_energy_grpc() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-perf)
    local rusage_logging_file=tmp-service.log

    local server_container_name=pocket-server-001
    local server_image=grpc_exp_shmem_server

    mkdir -p ${rusage_logging_dir}
    init_grpc
    sudo bash -c "echo 0 > /proc/sys/kernel/nmi_watchdog"

    # sudo python unix_multi_server.py &
    _run_d_server_grpc_rlimit_perf ${server_image} ${server_container_name} $NETWORK $TIMESTAMP 15
    local backend_uid=$(utils_get_container_id ${server_container_name})

    ./pocket/pocket \
        run \
            --perf $rusage_logging_dir \
            --no-ipc \
            -d \
            -b grpc_exp_shmem_client_perf \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=768mb \
            --cpus=1 \
            --volume=$(pwd)/data:/data \
            --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=$(pwd)/../yolov3-tf2-grpc/images:/img \
            --volume=$(pwd)/../yolov3-tf2-grpc:/root/yolov3-tf2 \
            --volume=$(pwd)/../tfrpc/client-grpc:/root/tfrpc/client \
            --network=$NETWORK \
            --env SERVER_ADDR=${SERVER_IP} \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env CONTAINER_ID=pocket-client-0000 \
            --env BACKEND_UID=${backend_uid} \
            --workdir='/root/yolov3-tf2' \
            -- perf stat -a -e power/energy-pkg/,power/energy-ram/ -o /data/$TIMESTAMP-${numinstances}-energy/pocket-client-0000.perf.log python3.6 detect.py --object path --image data/street.jpg


    sleep 5
    ./pocket/pocket \
        wait \
        pocket-client-0000

    docker ps -a

    sleep 5

    local perf_record_pid=$(sudo ./pocket/pocket \
        service \
        perf ${server_container_name} --dir ${rusage_logging_dir} --counters cpu-cycles,page-faults,minor-faults,major-faults,cache-misses,LLC-load-misses,LLC-store-misses,dTLB-load-misses,iTLB-load-misses)

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ./pocket/pocket \
            run \
                -d \
                --perf $rusage_logging_dir \
                --no-ipc \
                -b grpc_exp_shmem_client_perf \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=768mb \
                --cpus=1 \
                --volume=$(pwd)/data:/data \
                --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=$(pwd)/../yolov3-tf2-grpc/images:/img \
                --volume=$(pwd)/../yolov3-tf2-grpc:/root/yolov3-tf2 \
                --volume=$(pwd)/../tfrpc/client-grpc:/root/tfrpc/client \
                --network=$NETWORK \
                --env SERVER_ADDR=${SERVER_IP} \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env CONTAINER_ID=$container_name \
                --env BACKEND_UID=${backend_uid} \
                --workdir='/root/yolov3-tf2' \
                -- perf stat -a -e power/energy-pkg/,power/energy-ram/ -o /data/$TIMESTAMP-${numinstances}-energy/$container_name.perf.log python3.6 detect.py --object path --image data/street.jpg
        sleep $(generate_rand_num 3)
    done

    sudo bash -c "echo 1 > /proc/sys/kernel/nmi_watchdog"

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ./pocket/pocket \
            wait \
                ${container_name}
    done
    sudo kill -s INT $perf_record_pid

    ./pocket/pocket \
        service \
            kill ${server_container_name} \

    sleep 3

    # For debugging
    docker logs ${server_container_name}
    docker logs -f pocket-client-$(printf "%04d" $numinstances)
}

function measure_static_1() {
    # echo measure static!
    # exit
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-static1-cprofile)
    local rusage_logging_file=tmp-service.log

    local server_container_name=grpc_exp_server_shmem_00
    local server_image=grpc_exp_shmem_server

    mkdir -p ${rusage_logging_dir}

    init
    sudo kill -9 $(ps aux | grep unix_multi | awk '{print $2}') > /dev/null 2>&1
    sudo bash -c "echo 0 > /proc/sys/kernel/nmi_watchdog"

    sudo python unix_multi_server.py &
    _run_d_server_shmem_rlimit_static1_cProfile ${server_image} ${server_container_name} $TIMESTAMP 1.0 1024mb 15

    docker \
        run \
            -d \
            --ipc container:${server_container_name} \
            --memory=1024mb \
            --cpus=1 \
            --volume=$(pwd)/data:/data \
            --volume=$(pwd)/sockets:/sockets \
            --volume=$(pwd)/../yolov3-tf2/images:/img \
            --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
            --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
            --env SERVER_ADDR=${SERVER_IP} \
            --env CONTAINER_ID=grpc_exp_app_shmem_0000 \
            --workdir='/root/yolov3-tf2' \
            --name grpc_exp_app_shmem_0000 \
            grpc_exp_shmem_client \
            python3.6 -m cProfile -o /data/${TIMESTAMP}-static1-cprofile/${container_name}.cprofile detect.py --object path --image data/street.jpg

    docker \
        wait \
        grpc_exp_app_shmem_0000

    local start=$(date +%s.%N)
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=grpc_exp_app_shmem_${index}

        docker \
                run \
                    -d \
                    --ipc container:${server_container_name} \
                    --memory=1024mb \
                    --cpus=1 \
                    --volume=$(pwd)/data:/data \
                    --volume=$(pwd)/sockets:/sockets \
                    --volume=$(pwd)/../images:/img \
                    --volume=$(pwd)/..:/root/yolov3-tf2 \
                    --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
                    --env SERVER_ADDR=${SERVER_IP} \
                    --env CONTAINER_ID=${container_name} \
                    --workdir='/root/yolov3-tf2' \
                    --name ${container_name} \
                    grpc_exp_shmem_client \
                    python3.6 -m cProfile -o /data/${TIMESTAMP}-static1-cprofile/${container_name}.cprofile detect.py --object path --image data/street.jpg
        sleep $(generate_rand_num 3)
    done

    sudo bash -c "echo 1 > /proc/sys/kernel/nmi_watchdog"

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=grpc_exp_app_shmem_${index}

        docker wait ${container_name}
    done

    docker kill ${server_container_name} \

    sleep 3

    for filename in data/$TIMESTAMP-static1-cprofile/* ; do
        echo $filename
        if [[ "$filename" == *.cprofile ]]; then
            ./pocket/parseprof -f "$filename"
        fi
    done

    local end=$(date +%s.%N)
    local elapsed_time=$(echo $end - $start | tr -d $'\t' | bc)
    echo shmem $numinstances $start $end $elapsed_time >> data/end-to-end

    # For debugging
    docker logs grpc_exp_server_shmem_00
    docker logs -f grpc_exp_app_shmem_$(printf "%04d" $numinstances)
    # docker ps -a
    # ls /sys/fs/cgroup/memory/docker/
}

function measure_static_2() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-static2-cprofile)
    local rusage_logging_file=tmp-service.log

    local server_container_name=grpc_exp_server_shmem_00
    local server_image=grpc_exp_shmem_server

    mkdir -p ${rusage_logging_dir}

    init
    sudo kill -9 $(ps aux | grep unix_multi | awk '{print $2}') > /dev/null 2>&1
    sudo bash -c "echo 0 > /proc/sys/kernel/nmi_watchdog"

    sudo python unix_multi_server.py &
    _run_d_server_shmem_rlimit_static2_cProfile ${server_image} ${server_container_name} $TIMESTAMP 1.8 1843mb 15

    docker \
        run \
            -d \
            --ipc container:${server_container_name} \
            --memory=205mb \
            --cpus=0.2 \
            --volume=$(pwd)/data:/data \
            --volume=$(pwd)/sockets:/sockets \
            --volume=$(pwd)/../yolov3-tf2/images:/img \
            --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
            --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
            --env SERVER_ADDR=${SERVER_IP} \
            --env CONTAINER_ID=grpc_exp_app_shmem_0000 \
            --workdir='/root/yolov3-tf2' \
            --name grpc_exp_app_shmem_0000 \
            grpc_exp_shmem_client \
            python3.6 -m cProfile -o /data/${TIMESTAMP}-static2-cprofile/${container_name}.cprofile detect.py --object path --image data/street.jpg

    docker \
        wait \
        grpc_exp_app_shmem_0000

    local start=$(date +%s.%N)
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=grpc_exp_app_shmem_${index}

        docker \
                run \
                    -d \
                    --ipc container:${server_container_name} \
                    --memory=205mb \
                    --cpus=0.2 \
                    --volume=$(pwd)/data:/data \
                    --volume=$(pwd)/sockets:/sockets \
                    --volume=$(pwd)/../yolov3-tf2/images:/img \
                    --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
                    --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
                    --env SERVER_ADDR=${SERVER_IP} \
                    --env CONTAINER_ID=${container_name} \
                    --workdir='/root/yolov3-tf2' \
                    --name ${container_name} \
                    grpc_exp_shmem_client \
                    python3.6 -m cProfile -o /data/${TIMESTAMP}-static2-cprofile/${container_name}.cprofile detect.py --object path --image data/street.jpg
        sleep $(generate_rand_num 3)
    done

    sudo bash -c "echo 1 > /proc/sys/kernel/nmi_watchdog"

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=grpc_exp_app_shmem_${index}

        docker wait ${container_name}
    done

    docker kill ${server_container_name} \

    sleep 3

    for filename in data/$TIMESTAMP-static2-cprofile/* ; do
        echo $filename
        if [[ "$filename" == *.cprofile ]]; then
            ./pocket/parseprof -f "$filename"
        fi
    done

    local end=$(date +%s.%N)
    local elapsed_time=$(echo $end - $start | tr -d $'\t' | bc)
    echo shmem $numinstances $start $end $elapsed_time >> data/end-to-end

    # For debugging
    docker logs grpc_exp_server_shmem_00
    docker logs -f grpc_exp_app_shmem_$(printf "%04d" $numinstances)
    # docker ps -a
    # ls /sys/fs/cgroup/memory/docker/
}

function scaling_monolithic() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-scaling-monolithic)
    local rusage_logging_file=tmp-service.log

    mkdir -p ${rusage_logging_dir}
    init

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=yolo-monolithic-${index}

        docker \
            run \
            -d \
            --name ${container_name} \
            --memory=1024mb \
            --cpus=1.2 \
            --volume=$(pwd)/../yolov3-tf2-mono:/root/yolov3-tf2 \
            --workdir='/root/yolov3-tf2' \
            yolo-monolithic \
            python3.6 detect-loop-infinite.py path --image data/street.jpg --fps ${FPS} > /dev/null 2>&1
        sleep 3
    done
    sleep 30

    docker stats --no-stream

    # for i in $(seq 1 $numinstances); do
    #     local index=$(printf "%04d" $i)
    #     local container_name=yolo-monolithic-${index}

    #     ./pocket/pocket \
    #         rusage \
    #         measure ${container_name} --dir ${rusage_logging_dir} 
    # done

    # for file in ${rusage_logging_dir}/*; do
    #     cat $file | grep cpu_usage
    # done
    # for file in ${rusage_logging_dir}/*; do
    #     cat $file | grep max_memory_usage
    # done
    # for file in ${rusage_logging_dir}/*; do
    #     cat $file | grep pagefault
    # done
    # for file in ${rusage_logging_dir}/*; do
    #     cat $file | grep major_pagefault
    # done
    # For debugging
    # docker logs -f yolo-monolithic-$(printf "%04d" $numinstances)
}

function scaling() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-scaling)
    local rusage_logging_file=tmp-service.log

    local server_container_name=pocket-server-001
    local server_image=grpc_exp_shmem_server

    mkdir -p ${rusage_logging_dir}
    init
    _run_d_server_shmem_rlimit ${server_image} ${server_container_name} $NETWORK 15
    sleep 3

    # sudo ./pocket/pocket \
    #     rusage \
    #     init ${server_container_name} --dir ${rusage_logging_dir} 

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ./pocket/pocket \
            run \
                -d \
                -b grpc_exp_shmem_client \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=768mb \
                --cpus=1 \
                --volume=$(pwd)/data:/data \
                --volume $(pwd)/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=$(pwd)/../yolov3-tf2/images:/img \
                --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
                --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env CONTAINER_ID=${container_name} \
                --workdir='/root/yolov3-tf2' \
                -- python3.6 detect-loop-infinite.py --object path --fps ${FPS} --image data/street.jpg > /dev/null 2>&1
        sleep 5
    done
    sleep 30

    docker stats --no-stream

    # ./pocket/pocket \
    #     rusage \
    #     measure ${server_container_name} --dir ${rusage_logging_dir} 

    # for i in $(seq 1 $numinstances); do
    #     local index=$(printf "%04d" $i)
    #     local container_name=pocket-client-${index}

    #     ./pocket/pocket \
    #         rusage \
    #         measure ${container_name} --dir ${rusage_logging_dir} 
    # done

    sleep 3
    docker rm -f $(docker ps -aq)

    # utils_postprocess_server_rsuage_metric ${rusage_logging_dir}/tmp-pocket-server-001.log

    # echo server-results
    # for file in ${rusage_logging_dir}/*; do
    #     [[ "$file" = *server* ]] && cat $file | grep cpu_usage
    # done
    # for file in ${rusage_logging_dir}/*; do
    #     [[ "$file" = *server* ]] && cat $file | grep max_memory_usage
    # done
    # for file in ${rusage_logging_dir}/*; do
    #     [[ "$file" = *server* ]] && cat $file | grep pagefault | grep -v major
    # done
    # for file in ${rusage_logging_dir}/*; do
    #     [[ "$file" = *server* ]] && cat $file | grep major_pagefault
    # done

    # echo; echo client-results
    # for file in ${rusage_logging_dir}/*; do
    #     [[ "$file" = *server* ]] || cat $file | grep cpu_usage
    # done
    # for file in ${rusage_logging_dir}/*; do
    #     [[ "$file" = *server* ]] || cat $file | grep max_memory_usage
    # done
    # for file in ${rusage_logging_dir}/*; do
    #     [[ "$file" = *server* ]] || cat $file | grep pagefault | grep -v major
    # done
    # for file in ${rusage_logging_dir}/*; do
    #     [[ "$file" = *server* ]] || cat $file | grep major_pagefault
    # done
    # For debugging
    # docker logs -f yolo-monolithic-$(printf "%04d" $numinstances)
}

function cleanup_shm() {
    while IFS=$'\n' read -r line; do
        if [[ -z $line ]]; then
            continue
        fi
        semid=$(echo $line | awk '{print $2}')
        ipcrm -s $semid
    done <<< $(ipcs -s | tail -n +4)

    while IFS=$'\n' read -r line; do
        if [[ -z $line ]]; then
            continue
        fi
        shmid=$(echo $line | awk '{print $2}')
        ipcrm -m $shmid
    done <<< $(ipcs -m | tail -n +4)
}

function set_cgroup() {
    local mem_4g=4294967296
    local mem_8g=8589934592
    docker rm -f $(docker ps -q)
    sudo cgcreate -g memory:docker
    echo $mem_4g | sudo tee /sys/fs/cgroup/memory/docker/memory.limit_in_bytes
    local result=$?
    while [[ ! "$result" -eq "0" ]]; do
        sleep 3
        docker rm -f $(docker ps -q)
        sudo cgcreate -g memory:docker
        echo $mem_4g | sudo tee /sys/fs/cgroup/memory/docker/memory.limit_in_bytes
        result=$?
    done

    return
    # local cpusets="0,2,4,6,8,10"
    local cpusets="0,2,4,6,8,10,12,14,16,18"
    docker rm -f $(docker ps -q)
    sudo cgcreate -g cpuset:docker
    echo $cpusets | sudo tee /sys/fs/cgroup/cpuset/docker/cpuset.cpus
    local result=$?
    while [[ ! "$result" -eq "0" ]]; do
        sleep 3
        docker rm -f $(docker ps -q)
        sudo cgcreate -g cpuset:docker
        echo $cpusets | sudo tee /sys/fs/cgroup/cpuset/docker/cpuset.cpus
        result=$?
    done

    # or
    # cgcreate -g cpuset:misun-exp-cgroup
    # echo 0,2,4,6,8,10,12,14,16,18 | sudo tee /sys/fs/cgroup/cpuset/misun-exp-cgroup/cpuset.cpus
    # docker run -it --rm --cgroup-parent=/misun-exp-cgroup/ ubuntu bash
}

function recover_cgroup() {
    echo "0-47" | sudo tee /sys/fs/cgroup/cpuset/docker/cpuset.cpus
}

function help() {
    echo Usage: ./exp_script.sh COMMAND [OPTIONS]
    echo Supported Commands:
    echo -e '\thealth, help, build, rtt, cpu, pfault, cache, tlb, ...'
    echo example: bash ./exp_script.sh health
    echo example: bash ./exp_script.sh rtt
}

function env_set() {
    conda install -y absl-py
    pip install tensorflow==2.1.0
    pip opencv-python==4.1.1.26

    local current_dir=$(pwd)
    cd ..
    python convert.py
    git checkout experiments
    cd $current_dir

    cp -R ../yolov3-tf2/checkpoints ../tfrpc/server/
    cp ../tfrpc/client/pocket_tf_if.py ../tfrpc/server
}

trap finalize SIGINT
recover_cgroup
COMMAND=$([[ $# == 0 ]] && echo help || echo $1)
parse_arg ${@:2}

case $COMMAND in
    build)
        build_image
        ;;
    health|hello)
        health_check
        ;;
    'env-set')
        env_set
        ;;
    'latency-mon')
        measure_latency_monolithic $NUMINSTANCES
        ;;
    'rusage-mon')
        measure_rusage_monolithic $NUMINSTANCES
        ;;
    'perf-mon')
        measure_perf_monolithic $NUMINSTANCES
        ;;
    'energy-mon')
        measure_energy_monolithic $NUMINSTANCES
        ;;
    'latency-mon-warm')
        measure_latency_monolithic_warm $NUMINSTANCES
        ;;
    'thruput-mon')
        measure_thruput_monolithic $NUMINSTANCES
        ;;
    'latency')
        measure_latency $NUMINSTANCES
        ;;
    'thruput')
        measure_thruput $NUMINSTANCES
        ;;
    'rusage')
        measure_rusage $NUMINSTANCES
        ;;
    'cprofile')
        measure_cprofile $NUMINSTANCES
        ;;
    'perf')
        measure_perf $NUMINSTANCES
        ;;
    'energy')
        measure_energy $NUMINSTANCES
        ;;
    'latency-grpc')
        measure_latency_grpc $NUMINSTANCES
        ;;
    'rusage-grpc')
        measure_rusage_grpc $NUMINSTANCES
        ;;
    'perf-grpc')
        measure_perf_grpc $NUMINSTANCES
        ;;
    'energy-grpc')
        measure_energy_grpc $NUMINSTANCES
        ;;
    'cprofile-grpc')
        measure_cprofile_grpc $NUMINSTANCES
        ;;
    'measure-inference-throughput')
        measure_inf_thruput $NUMINSTANCES
        ;;
    'measure-inference-throughput-mon')
        measure_inf_thruput_monolithic $NUMINSTANCES
        ;;
    'perf-inf')
        perf_inf $NUMINSTANCES
        ;;
    'clean-data')
        rm -rf data/*
        ;;
    'motivation')
        # echo misun
        measure_static_1 $NUMINSTANCES
        measure_static_2 $NUMINSTANCES
        ;;
    'build-shmem')
        build_shmem
        ;;
    'cleanup-shm')
        cleanup_shm
        ;;
    'scaling-mon')
        scaling_monolithic $NUMINSTANCES
        ;;
    'scaling')
        scaling $NUMINSTANCES
        ;;
    'temp-exp')
        measure_latency2 $NUMINSTANCES
        ;;
    debug)
        init_ramfs
        ls ramfs
        ;;
    *|help)
        help
        ;;
esac
finalize
