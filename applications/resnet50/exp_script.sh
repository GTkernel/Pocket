#!/bin/bash

BASEDIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd ${BASEDIR}
NUMINSTANCES=1
TIMESTAMP=$(date +%Y%m%d-%H:%M:%S)
INTERVAL=0
RSRC_RATIO=0.5
RSRC_REALLOC=1
EVENTSET=0
FROM_SCRATCH=false

SUBNETMASK=111.222.0.0/16
SERVER_IP=111.222.3.26

PERF_COUNTERS=cpu-cycles,page-faults,minor-faults,major-faults,cache-misses,LLC-load-misses,LLC-store-misses,dTLB-load-misses,iTLB-load-misses,instructions

DEVICE=cpu
# POCKET_MEM_POLICY='func,ratio,0.5'      # (func/conn, ratio/minimum/none)
# POCKET_CPU_POLICY='func,ratio,0.5'      #
POCKET_MEM_POLICY='func,ratio,0.8'      # (func/conn, ratio/minimum/none)
POCKET_CPU_POLICY='func,ratio,0.8'      #
# POCKET_MEM_POLICY='func,none'      # (func/conn, ratio/minimum/none)
# POCKET_CPU_POLICY='func,none'      #
# POCKET_MEM_POLICY='conn,ratio,0.8'      # (func/conn, ratio/minimum/none)
# POCKET_CPU_POLICY='conn,ratio,0.8'      #


mkdir -p data

function parse_arg(){
    for arg in $@; do
        case $arg in
            -n=*|--num=*)
                NUMINSTANCES="${arg#*=}"
                ;;
            -s=*|--server=*)
                INTERVAL="${arg#*=}"
                ;;
            -ri=*|--random-interval=*)
                INTERVAL="${arg#*=}"
                ;;
            --fps=*)
                FPS="${arg#*=}"
                ;;
            -r=*|--ratio=*)
                RSRC_RATIO="${arg#*=}"
                ;;
            -ra=*|--resource-realloc=*)
                RSRC_REALLOC="${arg#*=}"
                ;;
            --event=*)
                EVENTSET="${arg#*=}"
                ;;
            --device=*)
                DEVICE="${arg#*=}"
                if [[ "$DEVICE" = "gpu" ]]; then
                    GPUS="--gpus 0"
                fi
                ;;
            --policy=*)
                POLICY_NO="${arg#*=}"
                case $POLICY_NO in
                    1)
                        POCKET_MEM_POLICY='func,ratio,0.8'      # (func/conn, ratio/minimum/none)
                        POCKET_CPU_POLICY='func,ratio,0.8'      #
                        ;;
                    2)
                        POCKET_MEM_POLICY='func,ratio,0.5'      # (func/conn, ratio/minimum/none)
                        POCKET_CPU_POLICY='func,ratio,0.5'      #
                        ;;
                    3)
                        POCKET_MEM_POLICY='func,none'      # (func/conn, ratio/minimum/none)
                        POCKET_CPU_POLICY='func,none'      #
                        ;;
                    4)
                        POCKET_MEM_POLICY='conn,ratio,0.8'      # (func/conn, ratio/minimum/none)
                        POCKET_CPU_POLICY='conn,ratio,0.8'      #
                        ;;
                esac
                ;;
            --mempolicy=*)
                POCKET_MEM_POLICY="${arg#*=}"
                ;;
            --cpupolicy=*)
                POCKET_CPU_POLICY="${arg#*=}"
                ;;
            --from-scratch)
                FROM_SCRATCH=true
                ;;
        esac
    done
}

function util_get_running_time() {
    local container_name=$1
    local start=$(docker inspect --format='{{.State.StartedAt}}' $container_name | xargs date +%s.%N -d)
    local end=$(docker inspect --format='{{.State.FinishedAt}}' $container_name | xargs date +%s.%N -d)
    local running_time=$(echo $end - $start | tr -d $'\t' | bc)

    echo $running_time
}

function utils_get_container_id() {
    local name=$1
    id=$(docker inspect -f '{{.Id}}' $name)
    echo $id
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

function run_server_basic() {
    local server_container_name=$1
    local server_ip=$2
    local server_image=$3
    eval docker run \
        -d \
        --privileged "${GPUS}" \
        --name=$server_container_name \
        --workdir='/root' \
        --env YOLO_SERVER=1 \
        --ip=$server_ip \
        --ipc=shareable \
        --cpus=$POCKET_BE_CPU \
        --memory=$POCKET_BE_MEM \
        --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
        --volume ${BASEDIR}/data:/data \
        --volume=${BASEDIR}/../../tfrpc/server:/root/tfrpc/server \
        --volume=/sys/fs/cgroup/:/cg \
        --volume=${BASEDIR}/../../resources/models:/models \
        $server_image \
        python tfrpc/server/yolo_server.py
}

function run_server_papi() {
    local server_container_name=$1
    local server_ip=$2
    local server_image=$3
    eval docker run \
        -d \
        --privileged "${GPUS}" \
        --name=$server_container_name \
        --workdir='/root' \
        --env YOLO_SERVER=1 \
        --ip=$server_ip \
        --ipc=shareable \
        --cpus=$POCKET_BE_CPU \
        --memory=$POCKET_BE_MEM \
        --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
        --volume $(pwd)/data:/data \
        --volume=$(pwd)/../scripts/sockets:/sockets \
        --volume=${BASEDIR}/../../tfrpc/server:/root/tfrpc/server \
        --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
        --volume=/sys/fs/cgroup/:/cg \
        --volume=${BASEDIR}/../../resources/models:/models \
        --env EVENTSET=$EVENTSET \
        --env NUM=$NUMINSTANCES \
        $server_image \
        python tfrpc/server/papi_server.py
}

function run_server_pf() {
    local server_container_name=$1
    local server_ip=$2
    local server_image=$3
    eval docker run \
        -d \
        --privileged "${GPUS}" \
        --name=$server_container_name \
        --workdir='/root' \
        --env YOLO_SERVER=1 \
        --ip=$server_ip \
        --ipc=shareable \
        --cpus=$POCKET_BE_CPU \
        --memory=$POCKET_BE_MEM \
        --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
        --volume $(pwd)/data:/data \
        --volume=$(pwd)/../scripts/sockets:/sockets \
        --volume=${BASEDIR}/../../tfrpc/server:/root/tfrpc/server \
        --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
        --volume=/sys/fs/cgroup/:/cg \
        --volume=${BASEDIR}/../../resources/models:/models \
        --env NUM=$NUMINSTANCES \
        $server_image \
        python tfrpc/server/pf_server.py
}

function run_server_cProfile() {
    local server_container_name=$1
    local server_ip=$2
    local server_image=$3
    local timestamp=$4
    local numinstances=$5
    eval docker run \
        -d \
        --privileged "${GPUS}" \
        --name=$server_container_name \
        --workdir='/root' \
        --env YOLO_SERVER=1 \
        --ip=$server_ip \
        --ipc=shareable \
        --cpus=1.0 \
        --memory=1024mb \
        --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
        --volume $(pwd)/data:/data \
        --volume=$(pwd)/../scripts/sockets:/sockets \
        --volume=${BASEDIR}/../../tfrpc/server:/root/tfrpc/server \
        --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
        $server_image \
        python -m cProfile -o /data/${timestamp}-${numinstances}-cprofile/${server_container_name}.cprofile tfrpc/server/yolo_server.py
}

function run_server_perf() {
    local server_container_name=$1
    local server_ip=$2
    local server_image=$3
    eval docker run \
        -d \
        --privileged "${GPUS}" \
        --name=$server_container_name \
        --workdir='/root' \
        --env YOLO_SERVER=1 \
        --ip=$server_ip \
        --ipc=shareable \
        --cpus=1.0 \
        --memory=1024mb \
        --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
        --volume $(pwd)/data:/data \
        --volume=$(pwd)/../scripts/sockets:/sockets \
        --volume=${BASEDIR}/../../tfrpc/server:/root/tfrpc/server \
        --volume=$(pwd)/../yolov3-tf2:/root/yolov3-tf2 \
        $server_image \
        python tfrpc/server/yolo_server.py
}

function init() {
    if [[ $FROM_SCRATCH = true ]]; then
        local containers="$(docker ps -a | grep "grpc_server\|grpc_app_\|grpc_exp_server\|grpc_exp_app\|pocket\|monolithic" | awk '{print $1}')"
    else
        local containers="$(docker ps -a | grep "grpc_server\|grpc_app_\|grpc_exp_server\|grpc_exp_app\|pocket" | awk '{print $1}')"
    fi
    docker stop ${containers} > /dev/null 2>&1
    docker wait ${containers} > /dev/null 2>&1

    [[ $FROM_SCRATCH = true ]] && docker container prune --force

    if [[ "$DEVICE" = "cpu" ]]; then
        POCKET_FE_CPU=1.3
        POCKET_FE_MEM=$(bc <<< '1024 * 0.25')mb
        POCKET_BE_CPU=1
        POCKET_BE_MEM=$(bc <<< '1024 * 1.1')mb
        # POCKET_BE_MEM=$(bc <<< '1024 * 2')mb
        MONOLITHIC_CPU=1.5
        MONOLITHIC_MEM=$(bc <<< '1024 * 1')mb
    elif [[ "$DEVICE" = "gpu" ]]; then
        POCKET_FE_CPU=0.8
        POCKET_FE_MEM=160mb
        POCKET_BE_CPU=1
        POCKET_BE_MEM=$(bc <<< '1024 * 2')mb
        MONOLITHIC_CPU=1
        MONOLITHIC_MEM=$(bc <<< '1024 * 1.8')mb
        # POCKET_FE_CPU=1.3
        # POCKET_FE_MEM=$(bc <<< '1024 * 0.25')mb
        # POCKET_BE_CPU=1
        # POCKET_BE_MEM=$(bc <<< '1024 * 2')mb
        # MONOLITHIC_CPU=1.5
        # MONOLITHIC_MEM=$(bc <<< '1024 * 1.6')mb
    fi

    # docker network rm $NETWORK
    # docker network create --driver=bridge --subnet=$SUBNETMASK $NETWORK
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

function help() {
    echo help!!!!!!!
}


function build_docker_files() {
    docker rmi -f pocket-resnet50-${DEVICE}-monolithic-perf
    docker image build --no-cache -t pocket-resnet50-${DEVICE}-monolithic-perf -f dockerfiles/${DEVICE}/Dockerfile.monolithic.perf dockerfiles/${DEVICE}

    docker rmi -f pocket-resnet50-${DEVICE}-monolithic-papi
    docker image build --no-cache -t pocket-resnet50-${DEVICE}-monolithic-papi -f dockerfiles/${DEVICE}/Dockerfile.monolithic.papi dockerfiles/${DEVICE}

    docker rmi -f pocket-resnet50-${DEVICE}-server
    docker image build -t pocket-resnet50-${DEVICE}-server -f dockerfiles/${DEVICE}/Dockerfile.pocket.ser dockerfiles/${DEVICE}

    docker rmi -f pocket-resnet50-${DEVICE}-application
    docker image build -t pocket-resnet50-${DEVICE}-application -f dockerfiles/${DEVICE}/Dockerfile.pocket.app dockerfiles/${DEVICE}

    docker rmi -f pocket-resnet50-${DEVICE}-perf-application
    docker image build --no-cache -t pocket-resnet50-${DEVICE}-perf-application -f dockerfiles/${DEVICE}/Dockerfile.pocket.perf.app dockerfiles/${DEVICE}

    docker rmi -f pocket-resnet50-${DEVICE}-monolithic
    docker image build -t pocket-resnet50-${DEVICE}-monolithic -f dockerfiles/${DEVICE}/Dockerfile.monolithic.perf dockerfiles/${DEVICE}

    docker rmi -f pocket-${DEVICE}-pypapi-server
    docker image build -t pocket-${DEVICE}-pypapi-server -f dockerfiles/${DEVICE}/Dockerfile.pocket.papi.ser dockerfiles/${DEVICE}

    rm -rf $(ls dockerfiles/${DEVICE} | grep -v Dockerfile)
}

function measure_latency() {
    local numinstances=$1
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-latency)

    local server_container_name=pocket-server-001
    local server_image=pocket-resnet50-${DEVICE}-server

    mkdir -p ${rusage_logging_dir}
    init

    run_server_basic $server_container_name $SERVER_IP $server_image
    sleep 5

    ../../pocket/pocket \
        run \
            --measure-latency $rusage_logging_dir \
            -d \
            -b pocket-resnet50-${DEVICE}-application \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=$(bc <<< '1024 * 2')mb \
            --cpus=5 \
            --volume=$(pwd)/data:/data \
            --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=${BASEDIR}/../../tfrpc/client:/root/tfrpc/client \
            --volume=$(pwd):/root/resnet50 \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env POCKET_MEM_POLICY=func,ratio,0.8 \
            --env POCKET_CPU_POLICY=func,ratio,0.8 \
            --env CONTAINER_ID=pocket-client-0000 \
            --workdir='/root/resnet50' \
            -- python3 app.pocket.py

    sleep 5
	../../pocket/pocket \
        wait pocket-client-0000


    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ../../pocket/pocket \
            run \
                --measure-latency $rusage_logging_dir \
                -d \
                -b pocket-resnet50-${DEVICE}-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=$POCKET_FE_MEM \
                --cpus=$POCKET_FE_CPU \
                --volume=$(pwd)/data:/data \
                --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=${BASEDIR}/../../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd):/root/resnet50 \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
                --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
                --env CONTAINER_ID=${container_name} \
                --workdir='/root/resnet50' \
                -- python3 app.pocket.py &
        interval=$(generate_rand_num 3)
        echo interval $interval
        sleep $interval
    done

    wait

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        ../../pocket/pocket \
            wait pocket-client-${index} > /dev/null 2>&1
    done

    # # For debugging
    # docker logs pocket-server-001
    # docker logs -f pocket-client-$(printf "%04d" $numinstances)

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker logs $container_name 2>&1 | grep "inference_time"
    done
}

function measure_latency_gpu() {
    local numinstances=$1
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-latency)

    local server_container_name=pocket-server-001
    local server_image=pocket-resnet50-${DEVICE}-server

    mkdir -p ${rusage_logging_dir}
    init

    run_server_basic $server_container_name $SERVER_IP $server_image
    sleep 5

    ../../pocket/pocket \
        run \
            --measure-latency $rusage_logging_dir \
            -d \
            -b pocket-resnet50-${DEVICE}-application \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=$(bc <<< '1024 * 2')mb \
            --cpus=5 \
            --volume=$(pwd)/data:/data \
            --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=${BASEDIR}/../../tfrpc/client:/root/tfrpc/client \
            --volume=$(pwd):/root/resnet50 \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env POCKET_MEM_POLICY=func,ratio,0.8 \
            --env POCKET_CPU_POLICY=func,ratio,0.8 \
            --env CONTAINER_ID=pocket-client-0000 \
            --workdir='/root/resnet50' \
            -- python3 app.pocket.gpu.py

    sleep 5
	../../pocket/pocket \
        wait pocket-client-0000


    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ../../pocket/pocket \
            run \
                --measure-latency $rusage_logging_dir \
                -d \
                -b pocket-resnet50-${DEVICE}-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=$POCKET_FE_MEM \
                --cpus=$POCKET_FE_CPU \
                --volume=$(pwd)/data:/data \
                --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=${BASEDIR}/../../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd):/root/resnet50 \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
                --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
                --env CONTAINER_ID=${container_name} \
                --workdir='/root/resnet50' \
                -- python3 app.pocket.gpu.py &
        interval=$(generate_rand_num 3)
        echo interval $interval
        sleep $interval
    done

    wait

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        ../../pocket/pocket \
            wait pocket-client-${index} > /dev/null 2>&1
    done

    # # For debugging
    # docker logs pocket-server-001
    # docker logs -f pocket-client-$(printf "%04d" $numinstances)

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker logs $container_name 2>&1 | grep "inference_time\|be_time\|fe_time"
    done
}

function measure_exec_breakdown() {
    local numinstances=$1
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-latency)

    local server_container_name=pocket-server-001
    local server_image=pocket-resnet50-${DEVICE}-server

    mkdir -p ${rusage_logging_dir}
    init

    run_server_basic $server_container_name $SERVER_IP $server_image
    sleep 5

    ../../pocket/pocket \
        run \
            --measure-latency $rusage_logging_dir \
            -d \
            -b pocket-resnet50-${DEVICE}-application \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=$(bc <<< '1024 * 2')mb \
            --cpus=5 \
            --volume=$(pwd)/data:/data \
            --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=${BASEDIR}/../../tfrpc/client:/root/tfrpc/client \
            --volume=$(pwd):/root/resnet50 \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env POCKET_MEM_POLICY=func,ratio,0.8 \
            --env POCKET_CPU_POLICY=func,ratio,0.8 \
            --env CONTAINER_ID=pocket-client-0000 \
            --workdir='/root/resnet50' \
            -- python3 app.pocket.execbd.py

    sleep 5
	../../pocket/pocket \
        wait pocket-client-0000


    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ../../pocket/pocket \
            run \
                --measure-latency $rusage_logging_dir \
                -d \
                -b pocket-resnet50-${DEVICE}-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=$POCKET_FE_MEM \
                --cpus=$POCKET_FE_CPU \
                --volume=$(pwd)/data:/data \
                --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=${BASEDIR}/../../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd):/root/resnet50 \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
                --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
                --env CONTAINER_ID=${container_name} \
                --workdir='/root/resnet50' \
                -- python3 app.pocket.execbd.py &
        interval=$(generate_rand_num 3)
        echo interval $interval
        sleep $interval
    done

    wait

    # # For debugging
    # docker logs pocket-server-001
    # docker logs -f pocket-client-$(printf "%04d" $numinstances)

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker logs $container_name 2>&1 | grep "total_time"
    done
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker logs $container_name 2>&1 | grep "be_time"
    done
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker logs $container_name 2>&1 | grep "fe_time"
    done
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker logs $container_name 2>&1 | grep "fe_ratio"
    done
}

function build_model() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-latency-monolithic)
    local rusage_logging_file=tmp-service.log

    mkdir -p ${rusage_logging_dir}
    init

    eval docker run "${GPUS}" \
        --name resnet50-monolithic-0000 \
        --cpus=$(bc <<< "$(lscpu | grep '^CPU(s):' | awk '{print $2}')/2") \
        --memory=$(bc <<< '1024 * 8')mb \
        --volume=$(pwd)/data:/data \
        --volume=$(pwd):/root/resnet50 \
        --volume=${BASEDIR}/../../resources/models:/models \
        --workdir=/root/resnet50 \
        pocket-resnet50-${DEVICE}-monolithic \
        python3 app.build_model.py

    # # For debugging
    # docker logs -f talkingheads-monolithic-$(printf "%04d" $numinstances)
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
    eval docker run "${GPUS}" \
        --name resnet50-monolithic-0000 \
        --cpus=1.5 \
        --memory=$(bc <<< '1024 * 1')mb \
        --volume=$(pwd)/data:/data \
        --volume=$(pwd):/root/resnet50 \
        --volume=${BASEDIR}/../../resources/models:/models \
        --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
        --workdir=/root/resnet50 \
        pocket-resnet50-${DEVICE}-monolithic \
        python3 app.monolithic.py >/dev/null 2>&1
        # python3 app.build_model.py

    running_time=$(util_get_running_time resnet50-monolithic-0000)
    echo $running_time > "${rusage_logging_dir}"/resnet50-monolithic-0000.latency

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}

        eval docker \
            run \
                -d "${GPUS}" \
                --name ${container_name} \
                --cpus=$MONOLITHIC_CPU \
                --memory=$MONOLITHIC_MEM \
                --volume=$(pwd)/data:/data \
                --volume=$(pwd):/root/resnet50 \
                --volume=${BASEDIR}/../../resources/models:/models \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --workdir=/root/resnet50 \
                pocket-resnet50-${DEVICE}-monolithic \
                python3 app.monolithic.py
        sleep $(generate_rand_num 3)
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}

        docker wait "${container_name}"
        running_time=$(util_get_running_time "${container_name}")
        echo $running_time > "${rusage_logging_dir}"/"${container_name}".latency
        echo $running_time
    done

    # local folder=$(realpath data/${TIMESTAMP}-${numinstances}-graph-monolithic)
    # mkdir -p $folder
    # for i in $(seq 0 $numinstances); do
    #     local index=$(printf "%04d" $i)
    #     local container_name=resnet50-monolithic-${index}
    #     docker logs $container_name 2>&1 | grep "graph_construction_time" > $folder/$container_name.graph
    # done

    # folder=$(realpath data/${TIMESTAMP}-${numinstances}-inf-monolithic)
    # mkdir -p $folder
    # for i in $(seq 0 $numinstances); do
    #     local index=$(printf "%04d" $i)
    #     local container_name=resnet50-monolithic-${index}
    #     docker logs $container_name 2>&1 | grep "inference_time" > $folder/$container_name.inf
    # done

    # # For debugging
    # docker logs -f resnet50-monolithic-$(printf "%04d" $numinstances)

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}
        docker logs $container_name 2>&1 | grep "inference_time"
    done
}

function measure_latency_monolithic_gpu() {
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
    eval docker run "${GPUS}" \
        --name resnet50-monolithic-0000 \
        --cpus=1.5 \
        --memory=$(bc <<< '1024 * 1')mb \
        --volume=$(pwd)/data:/data \
        --volume=$(pwd):/root/resnet50 \
        --volume=${BASEDIR}/../../resources/models:/models \
        --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
        --workdir=/root/resnet50 \
        pocket-resnet50-${DEVICE}-monolithic \
        python3 app.monolithic.gpu.py >/dev/null 2>&1
        # python3 app.build_model.py

    running_time=$(util_get_running_time resnet50-monolithic-0000)
    echo $running_time > "${rusage_logging_dir}"/resnet50-monolithic-0000.latency

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}

        eval docker \
            run \
                -d "${GPUS}" \
                --name ${container_name} \
                --cpus=$MONOLITHIC_CPU \
                --memory=$MONOLITHIC_MEM \
                --volume=$(pwd)/data:/data \
                --volume=$(pwd):/root/resnet50 \
                --volume=${BASEDIR}/../../resources/models:/models \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --workdir=/root/resnet50 \
                pocket-resnet50-${DEVICE}-monolithic \
                python3 app.monolithic.gpu.py
        sleep $(generate_rand_num 3)
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}

        docker wait "${container_name}"
        running_time=$(util_get_running_time "${container_name}")
        echo $running_time > "${rusage_logging_dir}"/"${container_name}".latency
        echo $running_time
    done

    # local folder=$(realpath data/${TIMESTAMP}-${numinstances}-graph-monolithic)
    # mkdir -p $folder
    # for i in $(seq 0 $numinstances); do
    #     local index=$(printf "%04d" $i)
    #     local container_name=resnet50-monolithic-${index}
    #     docker logs $container_name 2>&1 | grep "graph_construction_time" > $folder/$container_name.graph
    # done

    # folder=$(realpath data/${TIMESTAMP}-${numinstances}-inf-monolithic)
    # mkdir -p $folder
    # for i in $(seq 0 $numinstances); do
    #     local index=$(printf "%04d" $i)
    #     local container_name=resnet50-monolithic-${index}
    #     docker logs $container_name 2>&1 | grep "inference_time" > $folder/$container_name.inf
    # done

    # # For debugging
    # docker logs -f resnet50-monolithic-$(printf "%04d" $numinstances)

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}
        docker logs $container_name 2>&1 | grep "inference_time"
    done
}


function measure_papi() {
    local numinstances=$1
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-latency)

    local server_container_name=pocket-server-001
    local server_image=pocket-${DEVICE}-pypapi-server

    mkdir -p ${rusage_logging_dir}
    init

    run_server_papi $server_container_name $SERVER_IP $server_image
    sleep 3

    ../../pocket/pocket \
        run \
            --measure-latency $rusage_logging_dir \
            -d \
            -b pocket-resnet50-${DEVICE}-application \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=$(bc <<< '1024 * 0.25')mb \
            --cpus=1.3 \
            --volume=$(pwd)/data:/data \
            --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=${BASEDIR}/../../tfrpc/client:/root/tfrpc/client \
            --volume=$(pwd):/root/resnet50 \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
            --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
            --env CONTAINER_ID=pocket-client-0000 \
            --workdir='/root/resnet50' \
            -- python3 app.pocket.py

    sleep 5
	../../pocket/pocket \
        wait pocket-client-0000


    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ../../pocket/pocket \
            run \
                --measure-latency $rusage_logging_dir \
                -d \
                -b pocket-resnet50-${DEVICE}-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=$POCKET_FE_MEM \
                --cpus=$POCKET_FE_CPU \
                --volume=$(pwd)/data:/data \
                --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=${BASEDIR}/../../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd):/root/resnet50 \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
                --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
                --env CONTAINER_ID=${container_name} \
                --workdir='/root/resnet50' \
                -- python3 app.pocket.py &
        interval=$(generate_rand_num 3)
        echo interval $interval
        sleep $interval
    done

    wait

    # local folder=$(realpath data/${TIMESTAMP}-${numinstances}-graph)
    # mkdir -p $folder
    for i in $(seq 0 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker wait $container_name
    done
}

function measure_pf() {
    local numinstances=$1
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-latency)

    local server_container_name=pocket-server-001
    local server_image=pocket-resnet50-${DEVICE}-server

    mkdir -p ${rusage_logging_dir}
    init

    run_server_pf $server_container_name $SERVER_IP $server_image
    sleep 3

    ../../pocket/pocket \
        run \
            --measure-latency $rusage_logging_dir \
            -d \
            -b pocket-resnet50-${DEVICE}-application \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=$POCKET_FE_MEM \
            --cpus=$POCKET_FE_CPU \
            --volume=$(pwd)/data:/data \
            --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=${BASEDIR}/../../tfrpc/client:/root/tfrpc/client \
            --volume=$(pwd):/root/resnet50 \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
            --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
            --env CONTAINER_ID=pocket-client-0000 \
            --workdir='/root/resnet50' \
            -- python3 app.pocket.py

    sleep 5
	../../pocket/pocket \
        wait pocket-client-0000


    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ../../pocket/pocket \
            run \
                --measure-latency $rusage_logging_dir \
                -d \
                -b pocket-resnet50-${DEVICE}-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=$POCKET_FE_MEM \
                --cpus=$POCKET_FE_CPU \
                --volume=$(pwd)/data:/data \
                --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=${BASEDIR}/../../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd):/root/resnet50 \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
                --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
                --env CONTAINER_ID=${container_name} \
                --workdir='/root/resnet50' \
                -- python3 app.pocket.py &
        interval=$(generate_rand_num 3)
        echo interval $interval
        sleep $interval
    done

    wait

    # local folder=$(realpath data/${TIMESTAMP}-${numinstances}-graph)
    # mkdir -p $folder
    for i in $(seq 0 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker wait $container_name
    done
}


function measure_papi_monolithic() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-latency-monolithic)
    local rusage_logging_file=tmp-service.log

    mkdir -p ${rusage_logging_dir}
    init
    sudo sh -c 'echo -1 >/proc/sys/kernel/perf_event_paranoid'


    # docker run \
    #     --name resnet50-monolithic-0000 \
                # --cpus=1.5 \
                # --memory=$(bc <<< '1024 * 1')mb \
    #     --volume=$(pwd)/data:/data \
    #     --volume=$(pwd):/root/resnet50 \
    #     --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
    #     --workdir=/root/resnet50 \
    # --volume=${BASEDIR}/../../resources/models:/models \
    #     --cap-add CAP_SYS_ADMIN \
    #     --volume=${BASEDIR}/../../tfrpc/server/papi:/papi \
    #     --env EVENTSET=$EVENTSET \
    #     --env NUM=$NUMINSTANCES \
    #     pocket-resnet50-${DEVICE}-monolithic-papi \
    #     python3 app.monolithic.papi.py

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}

        eval docker \
            run \
                -d "${GPUS}" \
                --name ${container_name} \
                --cpus=$MONOLITHIC_CPU \
                --memory=$MONOLITHIC_MEM \
                --volume=$(pwd)/data:/data \
                --volume=$(pwd):/root/resnet50 \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --workdir=/root/resnet50 \
                --volume=${BASEDIR}/../../resources/models:/models \
                --cap-add CAP_SYS_ADMIN \
                --volume=${BASEDIR}/../../tfrpc/server/papi:/papi \
                --env EVENTSET=$EVENTSET \
                --env NUM=$NUMINSTANCES \
                pocket-resnet50-${DEVICE}-monolithic-papi \
                python3 app.monolithic.papi.py
        sleep $(generate_rand_num 3)
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}

        docker wait "${container_name}"
    done

    sudo sh -c 'echo 3 >/proc/sys/kernel/perf_event_paranoid'


    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}
        docker logs $container_name 2>&1 | grep "inference_time"
    done
}

function measure_pf_monolithic() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-latency-monolithic)
    local rusage_logging_file=tmp-service.log

    mkdir -p ${rusage_logging_dir}
    init

    # docker run \
    #     --name resnet50-monolithic-0000 \
                # --cpus=1.5 \
                # --memory=$(bc <<< '1024 * 1')mb \
    #     --volume=$(pwd)/data:/data \
    #     --volume=$(pwd):/root/resnet50 \
    #     --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
    #     --workdir=/root/resnet50 \
                    # --volume=${BASEDIR}/../../resources/models:/models \
    #     --env NUM=$NUMINSTANCES \
    #     pocket-resnet50-${DEVICE}-monolithic-papi \
    #     python3 app.monolithic.pf.py
    #     # --cap-add CAP_SYS_ADMIN \

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}

        eval docker \
            run \
                -d "${GPUS}" \
                --name ${container_name} \
                --cpus=$MONOLITHIC_CPU \
                --memory=$MONOLITHIC_MEM \
                --volume=$(pwd)/data:/data \
                --volume=$(pwd):/root/resnet50 \
                --volume=${BASEDIR}/../../resources/models:/models \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --workdir=/root/resnet50 \
                --env NUM=$NUMINSTANCES \
                pocket-resnet50-${DEVICE}-monolithic-papi \
                python3 app.monolithic.pf.py
        sleep $(generate_rand_num 3)
    done
    
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}

        docker wait "${container_name}"
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}
        docker logs $container_name 2>&1 | grep "inference_time"
    done
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
            --name resnet50-monolithic-0000 \
            --cpus=1 \
            --memory=512mb \
            --volume=$(pwd)/data:/data \
            --volume=$(pwd):/root/resnet50 \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --workdir=/root/resnet50 \
            pocket-resnet50-${DEVICE}-monolithic \
            bash

    docker \
        exec \
            resnet50-monolithic-0000 \
            python3 app.monolithic.py

    ../../pocket/pocket \
        rusage \
        measure resnet50-monolithic-0000 --dir ${rusage_logging_dir} 



    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}

        docker \
            run \
                -di \
                --name ${container_name} \
                --cpus=1 \
                --memory=512mb \
                --volume=$(pwd)/data:/data \
                --volume=$(pwd):/root/resnet50 \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --workdir=/root/resnet50 \
                pocket-resnet50-${DEVICE}-monolithic \
                bash
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}

        docker \
            exec \
                ${container_name} \
                python3 app.monolithic.py
        sleep $(generate_rand_num 3)
    done

    wait

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}

        ../../pocket/pocket \
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
            -di \
            --name resnet50-monolithic-0000 \
            --cpus=1 \
            --memory=512mb \
            --volume=$(pwd)/data:/data \
            --volume=$(pwd):/root/resnet50 \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --cap-add SYS_ADMIN \
            --cap-add IPC_LOCK \
            --workdir=/root/resnet50 \
            pocket-resnet50-${DEVICE}-monolithic-perf \
            perf stat -e ${PERF_COUNTERS} -o /data/$TIMESTAMP-${numinstances}-perf-monolithic/resnet50-monolithic-0000.perf.log python3 app.monolithic.py

    docker \
        wait \
            resnet50-monolithic-0000

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}

        docker \
            run \
                -di \
                --name ${container_name} \
                --cpus=1 \
                --memory=512mb \
                --volume=$(pwd)/data:/data \
                --volume=$(pwd):/root/resnet50 \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --cap-add SYS_ADMIN \
                --cap-add IPC_LOCK \
                --workdir=/root/resnet50 \
                pocket-resnet50-${DEVICE}-monolithic-perf \
                perf stat -e ${PERF_COUNTERS} -o /data/$TIMESTAMP-${numinstances}-perf-monolithic/${container_name}.perf.log python3 app.monolithic.py
        sleep $(generate_rand_num 3)
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}

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
    local server_image=pocket-resnet50-${DEVICE}-server

    mkdir -p ${rusage_logging_dir}
    init
    run_server_basic $server_container_name $SERVER_IP $server_image

    ### rusage measure needs 'd' flag
    ../../pocket/pocket \
        run \
            --rusage $rusage_logging_dir \
            -d \
            -b pocket-resnet50-${DEVICE}-application \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=512mb \
            --cpus=1 \
            --volume=$(pwd)/data:/data \
            --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=${BASEDIR}/../../tfrpc/client:/root/tfrpc/client \
            --volume=$(pwd):/root/resnet50 \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env CONTAINER_ID=pocket-client-0000 \
            --workdir='/root/resnet50' \
            -- python3 app.pocket.py &

    ../../pocket/pocket \
        wait \
        pocket-client-0000

    sleep 5

    sudo ../../pocket/pocket \
        rusage \
        init ${server_container_name} --dir ${rusage_logging_dir} 

    ### Firing multiple instances with rusage flag requires & at the end.
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ../../pocket/pocket \
            run \
                --rusage $rusage_logging_dir \
                -d \
                -b pocket-resnet50-${DEVICE}-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=512mb \
                --cpus=1 \
                --volume=$(pwd)/data:/data \
                --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=${BASEDIR}/../../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd):/root/resnet50 \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env CONTAINER_ID=${container_name} \
                --workdir='/root/resnet50' \
                -- python3 app.pocket.py &
        sleep $(generate_rand_num 3)
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        # docker wait "${container_name}"
        ../../pocket/pocket \
            wait \
                ${container_name}
    done

    ../../pocket/pocket \
        rusage \
        measure ${server_container_name} --dir ${rusage_logging_dir} 
}

function measure_cprofile() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-cprofile)
    local rusage_logging_file=tmp-service.log

    local server_container_name=pocket-server-001
    local server_image=pocket-resnet50-${DEVICE}-server

    mkdir -p ${rusage_logging_dir}
    init
    run_server_cProfile $server_container_name $SERVER_IP $server_image $TIMESTAMP $numinstances

    ../../pocket/pocket \
        run \
            --cprofile $rusage_logging_dir \
            -d \
            -b pocket-resnet50-${DEVICE}-application \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=512mb \
            --cpus=1 \
            --volume=$(pwd)/data:/data \
            --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=${BASEDIR}/../../tfrpc/client:/root/tfrpc/client \
            --volume=$(pwd):/root/resnet50 \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env CONTAINER_ID=pocket-client-0000 \
            --workdir='/root/resnet50' \
            -- python3.6 -m cProfile -o /data/${TIMESTAMP}-${numinstances}-cprofile/pocket-client-0000.cprofile app.pocket.py

    ../../pocket/pocket \
        wait \
        pocket-client-0000

    sleep 5

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ../../pocket/pocket \
            run \
                --cprofile $rusage_logging_dir \
                -d \
                -b pocket-resnet50-${DEVICE}-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=512mb \
                --cpus=1 \
                --volume=$(pwd)/data:/data \
                --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=${BASEDIR}/../../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd):/root/resnet50 \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env CONTAINER_ID=${container_name} \
                --workdir='/root/resnet50' \
                -- python3.6 -m cProfile -o /data/${TIMESTAMP}-${numinstances}-cprofile/${container_name}.cprofile app.pocket.py
        sleep $(generate_rand_num 3)
    done

    sudo bash -c "echo 1 > /proc/sys/kernel/nmi_watchdog"

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ../../pocket/pocket \
            wait \
                ${container_name}
    done

    ../../pocket/pocket \
        service \
            kill ${server_container_name} \

    sleep 3

    for filename in data/$TIMESTAMP-${numinstances}-cprofile/* ; do
        echo $filename
        if [[ "$filename" == *.cprofile ]]; then
            ../scripts/pocket/parseprof -f "$filename"
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
    local server_image=pocket-resnet50-${DEVICE}-server

    mkdir -p ${rusage_logging_dir}
    init
    sudo bash -c "echo 0 > /proc/sys/kernel/nmi_watchdog"

    # sudo python unix_multi_server.py &
    run_server_perf $server_container_name $SERVER_IP $server_image

    ../../pocket/pocket \
        run \
            --perf $rusage_logging_dir \
            -d \
            -b pocket-resnet50-${DEVICE}-perf-application \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=512mb \
            --cpus=1 \
            --volume=$(pwd)/data:/data \
            --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=${BASEDIR}/../../tfrpc/client:/root/tfrpc/client \
            --volume=$(pwd):/root/resnet50 \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env CONTAINER_ID=pocket-client-0000 \
            --workdir='/root/resnet50' \
            -- perf stat -e ${PERF_COUNTERS} -o /data/$TIMESTAMP-${numinstances}-perf/pocket-client-0000.perf.log python3.6 app.pocket.py

    sleep 5
    ../../pocket/pocket \
        wait \
        pocket-client-0000

    sleep 5

    local perf_record_pid=$(sudo ../../pocket/pocket \
        service \
        perf ${server_container_name} --dir ${rusage_logging_dir} --counters cpu-cycles,page-faults,minor-faults,major-faults,cache-misses,LLC-load-misses,LLC-store-misses,dTLB-load-misses,iTLB-load-misses)

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ../../pocket/pocket \
            run \
                -d \
                --perf $rusage_logging_dir \
                -b pocket-resnet50-${DEVICE}-perf-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=512mb \
                --cpus=1 \
                --volume=$(pwd)/data:/data \
                --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=${BASEDIR}/../../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd):/root/resnet50 \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env CONTAINER_ID=${container_name} \
                --workdir='/root/resnet50' \
                -- perf stat -e ${PERF_COUNTERS} -o /data/$TIMESTAMP-${numinstances}-perf/$container_name.perf.log python3.6 app.pocket.py
        sleep $(generate_rand_num 3)
    done

    sudo bash -c "echo 1 > /proc/sys/kernel/nmi_watchdog"

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ../../pocket/pocket \
            wait \
                ${container_name}
    done
    sudo kill -s INT $perf_record_pid

    ../../pocket/pocket \
        service \
            kill ${server_container_name} \

    sleep 3

    # For debugging
    docker logs ${server_container_name}
    docker logs -f pocket-client-$(printf "%04d" $numinstances)
}


function boottime() {
    local numinstances=$1
    local server_container_name=pocket-server-001
    local server_image=pocket-resnet50-${DEVICE}-server
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-perf)

    mkdir -p ${rusage_logging_dir}
    init

    run_server_basic $server_container_name $SERVER_IP $server_image
    sleep 5

    ../../pocket/pocket \
        run \
            --measure-latency $rusage_logging_dir \
            -d \
            -b pocket-resnet50-${DEVICE}-application \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=2048mb \
            --cpus=5 \
            --volume=$(pwd)/data:/data \
            --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
            --volume=${BASEDIR}/../../tfrpc/client:/root/tfrpc/client \
            --volume=$(pwd):/root/resnet50 \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env POCKET_MEM_POLICY=func,ratio,0.8 \
            --env POCKET_CPU_POLICY=func,ratio,0.8 \
            --env CONTAINER_ID=pocket-client-0000 \
            --workdir='/root/resnet50' \
            -- python3 app.pocket.py

    sleep 5
    ../../pocket/pocket \
        wait pocket-client-0000

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ### 1. Instantiate
        echo "[parse/boot/resnet50/poc/$i/init] $(date +%s%6N)"
        ../../pocket/pocket \
            run \
                --measure-latency $rusage_logging_dir \
                -d \
                -b pocket-resnet50-${DEVICE}-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=$POCKET_FE_MEM \
                --cpus=$POCKET_FE_CPU \
                --volume=$(pwd)/data:/data \
                --volume=${BASEDIR}/../../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=${BASEDIR}/../../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd):/root/resnet50 \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
                --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
                --env CONTAINER_ID=${container_name} \
                --workdir='/root/resnet50' \
                -- bash -c "echo -n '[parse/boot/resnet50/poc/$i/boot] ' && date +%s%6N && python3 app.pocket.boot.py" &
        interval=$(generate_rand_num 3)
        echo interval $interval
        sleep $interval
    done

    wait

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        ../../pocket/pocket \
            wait pocket-client-${index} > /dev/null 2>&1
    done

    # # For debugging
    # docker logs pocket-server-001
    # docker logs -f pocket-client-$(printf "%04d" $numinstances)

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker logs $container_name 2>&1 | grep '\[parse/boot'
    done
    rm -rf "${rusage_logging_dir}"
}

function boottime_monolithic() {
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
    eval docker run "${GPUS}" \
        --name resnet50-monolithic-0000 \
        --cpus=1.5 \
        --memory=$(bc <<< '1024 * 0.3')mb \
        --volume=$(pwd)/data:/data \
        --volume=$(pwd):/root/resnet50 \
        --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
        --workdir=/root/resnet50 \
        pocket-resnet50-${DEVICE}-monolithic \
        python3 app.monolithic.py >/dev/null 2>&1

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}

        echo "[parse/boot/resnet50/mon/$i/init] $(date +%s%6N)"
        eval docker \
            run \
                -d "${GPUS}" \
                --name ${container_name} \
                --cpus=$MONOLITHIC_CPU \
                --memory=$MONOLITHIC_MEM \
                --volume=$(pwd)/data:/data \
                --volume=$(pwd):/root/resnet50 \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env CONTAINER_ID=$i \
                --workdir=/root/resnet50 \
                pocket-resnet50-${DEVICE}-monolithic \
                bash -c \"echo -n \'[parse/boot/resnet50/mon/$i/boot] \' \&\& date +%s%6N \&\& python3 app.monolithic.boot.py\"
                # bash -c \"python3 app.monolithic.boot.py\"
                # python3 app.monolithic.boot.py
                # which python3
                # pwd
                # bash -c "which python3"
                # python3 app.monolithic.boot.py
        sleep $(generate_rand_num 3)
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}

        docker wait "${container_name}"
        # running_time=$(util_get_running_time "${container_name}")
        # echo $running_time > "${rusage_logging_dir}"/"${container_name}".latency
        # echo $running_time
    done

    # # For debugging
    # docker logs -f resnet50-monolithic-$(printf "%04d" $numinstances)
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}
        docker logs $container_name 2>&1 | grep '\[parse/boot'
    done

    rm -rf $rusage_logging_dir
}

function boottime_monolithic_cr() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-latency-monolithic)
    local rusage_logging_file=tmp-service.log

    mkdir -p ${rusage_logging_dir}
    init

    ipcrm --all=msg && sleep 3

    # 1. Remove all existing checkpoints
    if [[ $FROM_SCRATCH = true ]]; then
        for i in $(seq 1 $numinstances); do
            local index=$(printf "%04d" $i)
            local container_name=resnet50-monolithic-${index}

            docker rm -f ${container_name} > /dev/null 2>&1
            docker checkpoint rm ${container_name} default > /dev/null 2>&1
        done
        sudo rm -rf /tmp/*checkpoint* && sudo systemctl restart docker
    fi

    
    # 2. Create a checkpoint
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}

        local checkpoints=$(docker checkpoint ls ${container_name} | wc -l)
        if [[ $checkpoints -ge 2 ]]; then
            continue
        fi

        kill -n 15 $(ps aux | grep create\_checkpoint | awk '{ print $2 }') > /dev/null 2>&1
        python3 ../../scripts/utils/create_checkpoint.py &
        pid_checkpoint_helper=$!
        sleep 3

        eval docker \
            run \
                -d "${GPUS}" \
                --name ${container_name} \
                --cpus=$MONOLITHIC_CPU \
                --memory=$MONOLITHIC_MEM \
                --ipc=host \
                --volume=$(pwd)/data:/data \
                --volume=$(pwd):/root/resnet50 \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env CONTAINER_ID=$i \
                --env CONTAINER_NAME=${container_name} \
                --workdir=/root/resnet50 \
                pocket-resnet50-${DEVICE}-monolithic \
                bash -c \"echo -n \'[parse/boot/resnet50/cr/$i/boot] \' \&\& date +%s%6N \&\& python3 app.monolithic.cr.boot.py\"

        wait $pid_checkpoint_helper
        docker wait ${container_name} > /dev/null 2>&1
    done

    # 3. start a check point
    local startat=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    sleep 1
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}

        echo "[parse/boot/resnet50/cr/$i/init] $(date +%s%6N)"
        docker \
            start \
                --checkpoint default ${container_name}
        sleep $(generate_rand_num 3)
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}

        docker wait "${container_name}"
    done

    kill -SIGTERM $strace_pid

    # # For debugging
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=resnet50-monolithic-${index}

        docker logs $container_name --since $startat 2>&1 | grep '\[parse/boot'
    done

    rm -rf $rusage_logging_dir
}


parse_arg ${@:2}
echo '>>>>>>>POCKET_MEM_POLICY=' $POCKET_MEM_POLICY
echo '>>>>>>>POCKET_CPU_POLICY=' $POCKET_CPU_POLICY
COMMAND=$1

case $COMMAND in
    build)
        build_docker_files
        ;;
    'latency-mon')
        measure_latency_monolithic $NUMINSTANCES
        ;;
    'latency-mon-gpu')
        measure_latency_monolithic_gpu $NUMINSTANCES
        ;;
    'rusage-mon')
        measure_rusage_monolithic $NUMINSTANCES
        ;;
    'perf-mon')
        measure_perf_monolithic $NUMINSTANCES
        ;;
    'latency')
        measure_latency $NUMINSTANCES
        ;;
    'latency-gpu')
        measure_latency_gpu $NUMINSTANCES
        ;;
    'measure-exec')
        measure_exec_breakdown $NUMINSTANCES
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
    'papi-mon')
        measure_papi_monolithic $NUMINSTANCES
        ;;
    'pf-mon')
        measure_pf_monolithic $NUMINSTANCES
        ;;
    'papi')
        measure_papi $NUMINSTANCES
        ;;
    'pf')
        measure_pf $NUMINSTANCES
        ;;
    'boottime')
        boottime $NUMINSTANCES
        ;;
    'boottime-mon')
        boottime_monolithic $NUMINSTANCES
        ;;
    'boottime-mon-cr')
        boottime_monolithic_cr $NUMINSTANCES
        ;;
    'help'|*)
        help
        ;;

esac