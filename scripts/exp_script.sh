#!/bin/bash

BASEDIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
POCKET="../pocket/pocket"
CC_POCKET_EXPERIMENT=0
APPLICATION=ssdresnet50v1
APPLICATIONS=()
APPDIR=ssdresnet50v1_640x640
cd ${BASEDIR}
NUMINSTANCES=1
TIMESTAMP=$(date +%Y%m%d-%H:%M:%S)
INTERVAL=0
RSRC_RATIO=0.5
RSRC_REALLOC=1
EVENTSET=0
RUSAGE_MEASURE=0
RESOURCE_CONFIG_FILE=resource_config
TF_SERVER=1

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

# with get_app_value
if [[ "$DEVICE" = "cpu" ]]; then
    POCKET_FE_MEM_PRESET=(1 0.125 0.25 0.25 0.5 0.25 0.5)
    POCKET_FE_CPU_PRESET=(1 1.3 1.3 1.3 1.3 1.7 1.7)
    POCKET_BE_MEM_PRESET=(1 0.4 1.1 1.1 0.9 2.2 1.4)
    POCKET_BE_MEM_SWAP_PRESET=(1 1.6 4.4 4.4 8.8 5.6)
    POCKET_BE_CPU_PRESET=(1 1 1 1 1 2 2.5)

    MONOLITHIC_MEM_PRESET=(1 0.3 1 1 0.9 2.2 1.3)
    MONOLITHIC_CPU_PRESET=(1 1.5 1.5 1.5 1.5 2 2)
else
# currently same as cpu.. todo: update.
    POCKET_FE_MEM_PRESET=(1 0.125 0.25 0.25 0.5 0.25 0.5)
    POCKET_FE_CPU_PRESET=(1 1.3 1.3 1.3 1.3 1.7 1.7)
    POCKET_BE_MEM_PRESET=(1 0.4 1.1 1.1 0.9 2.2 1.4)
    POCKET_BE_MEM_SWAP_PRESET=(1 1.6 4.4 4.4 8.8 5.6)
    POCKET_BE_CPU_PRESET=(1 1 1 1 1 2 2.5)
fi

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
                        POCKET_MEM_POLICY='conn,ratio,0.5'      # (func/conn, ratio/minimum/none)
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
            --squeeze)
                SQUEEZE=1
                ;;
            --rusage)
                RUSAGE_MEASURE=1
                ;;
            -a=*|--app=*)
                APPLICATION="${arg#*=}"
                APPDIR=$(get_application_dir $APPLICATION)
                ;;
            --resource-config=*)
                RESOURCE_CONFIG_FILE="${arg#*=}"
                ;;
            --apps=*)
                IFS=',' read -r -a APPLICATIONS <<< "${arg#*=}"
                ;;
            --tf-server=*)
                TF_SERVER="${arg#*=}"
                ;;
            --cpu-multiplier=*)
                CPU_MULTIPLIER="${arg#*=}"
                ;;
            *)
                echo Unknown argument: ${arg}
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

function get_max_be_mem() {
    local sum=0.25
    for app in ${APPLICATIONS[@]}; do
        local model_size=0
        case $app in
            mobilenetv2)
                model_size=0.2
                ;;
            resnet50)
                model_size=0.45
                ;;
            ssdmobilenetv2)
                model_size=0.82
                ;;
            ssdresnet50v1)
                model_size=1.3
                ;;
            smallbert)
                model_size=0.75
                ;;
            talkingheads)
                model_size=2
                ;;
            *)
                echo no such model: $app
                exit -1
                ;;
        esac
        sum=$(bc <<< "$sum + $model_size ")
    done
    local less_than_1=$(bc <<< "$sum < 1")
    sum=$([[ $less_than_1 = "1" ]] && echo 0$sum || echo $sum)
    echo $sum
}

function get_application_dir() {
    local app=$1
    case $app in
        mobilenetv2)
            echo mobilenetv2
            ;;
        resnet50)
            echo resnet50
            ;;
        smallbert)
            echo smallbert
            ;;
        talkingheads)
            echo talkingheads
            ;;
        ssdmobilenetv2)
            echo ssdmobilenetv2_320x320
            ;;
        ssdresnet50v1)
            echo ssdresnet50v1_640x640
            ;;
        *)
            echo No such application!
            exit -1
            ;;
    esac
}

function get_largest_app() {
    local max_value=0
    for app in ${APPLICATIONS[@]}; do
        local app_value=$(get_app_value ${app})
        if [[ ${app_value} -gt ${max_value} ]]; then
            max_value=${app_value}
        fi
    done
    max_app=$(value_to_app $max_value)
    echo $max_app
}

function get_app_value() {
    local app_name=$1
    case $app_name in
        mobilenetv2)
            echo 1
            ;;
        resnet50)
            echo 2
            ;;
        smallbert)
            echo 3
            ;;
        talkingheads)
            echo 5
            ;;
        ssdmobilenetv2)
            echo 4
            ;;
        ssdresnet50v1)
            echo 6
            ;;
        *)
            echo No such application!
            exit -1
            ;;
    esac
}

function value_to_app() {
    local app_value=$1
    case $app_value in
        1)
            echo mobilenetv2
            ;;
        2)
            echo resnet50
            ;;
        3)
            echo smallbert
            ;;
        5)
            echo talkingheads
            ;;
        4)
            echo ssdmobilenetv2
            ;;
        6)
            echo ssdresnet50v1
            ;;
        *)
            echo No such application!
            exit -1
            ;;
    esac
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
        --memory-swap=$POCKET_BE_MEM_SWAP \
        --volume $(pwd -P)/../applications/${APPDIR}/data:/data \
        --volume=$(pwd -P)/../tfrpc/server:/root/tfrpc/server \
        --volume=$(pwd -P)/../yolov3-tf2:/root/yolov3-tf2 \
        --volume=/sys/fs/cgroup/:/cg \
        --volume=${BASEDIR}/../../resources/models:/models \
        $server_image \
        python tfrpc/server/yolo_server.py
        # --volume=$(pwd -P)/../scripts/sockets:/sockets \ ## needed for gRPC.
        # --volume $(pwd -P)/../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \ ## needed for pocket with daemon
}

function run_server_isolation_config() {
    local server_container_name=$1
    local server_ip=$2
    local server_image=$3
    local isolation_config=''
    IFS=',' read -r -a isolation_config <<< $4
    local nscreate=off
    local private_queue=off
    local acl=off

    for iso_config in ${isolation_config[@]}; do
        case $iso_config in
            ns)
                nscreate=on
                ;;
            pq)
                private_queue=on
                ;;
            acl)
                acl=on
                ;;
        esac
    done

    eval docker run \
        -d \
        --privileged "${GPUS}" \
        --name=$server_container_name \
        --workdir='/root' \
        --env YOLO_SERVER=1 \
        --env NSCREATE=$nscreate \
        --env CAPABILITIESLIST=$acl \
        --env PRIVATEQUEUE=$private_queue \
        --ip=$server_ip \
        --ipc=shareable \
        --cpus=$POCKET_BE_CPU \
        --memory=$POCKET_BE_MEM \
        --memory-swap=$POCKET_BE_MEM_SWAP \
        --volume $(pwd -P)/../applications/${APPDIR}/data:/data \
        --volume=$(pwd -P)/../tfrpc/server:/root/tfrpc/server \
        --volume=$(pwd -P)/../yolov3-tf2:/root/yolov3-tf2 \
        --volume=/sys/fs/cgroup/:/cg \
        --volume=${BASEDIR}/../../resources/models:/models \
        $server_image \
        python tfrpc/server/yolo_server_isolation.py
        # --volume=$(pwd -P)/../scripts/sockets:/sockets \ ## needed for gRPC.
        # --volume $(pwd -P)/../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \ ## needed for pocket with daemon
}

function run_server_nop() {
    local server_container_name=$1
    local server_ip=$2
    local server_image=$3
    eval docker run \
        -d \
        --privileged "${GPUS}" \
        --name=$server_container_name \
        --workdir='/root' \
        --env YOLO_SERVER=1 \
        --env TF_SERVER=${TF_SERVER} \
        --ip=$server_ip \
        --ipc=shareable \
        --cpus=$POCKET_BE_CPU \
        --memory=$POCKET_BE_MEM \
        --memory-swap=$POCKET_BE_MEM_SWAP \
        --volume $(pwd -P)/../applications/${APPDIR}/data:/data \
        --volume=$(pwd -P)/../tfrpc/server:/root/tfrpc/server \
        --volume=$(pwd -P)/../yolov3-tf2:/root/yolov3-tf2 \
        --volume=/sys/fs/cgroup/:/cg \
        --volume=${BASEDIR}/../../resources/models:/models \
        $server_image \
        python tfrpc/server/nop_server.py
        # --volume=$(pwd -P)/../scripts/sockets:/sockets \ ## needed for gRPC.
        # --volume $(pwd -P)/../pocket/tmp/pocketd.sock:/tmp/pocketd.sock \ ## needed for pocket with daemon
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
        --memory-swap=$POCKET_BE_MEM_SWAP \
        --volume $(pwd -P)/../applications/${APPDIR}/data:/data \
        --volume=$(pwd -P)/../tfrpc/server:/root/tfrpc/server \
        --volume=$(pwd -P)/../yolov3-tf2:/root/yolov3-tf2 \
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
        --memory-swap=$POCKET_BE_MEM_SWAP \
        --volume $(pwd -P)/../applications/${APPDIR}/data:/data \
        --volume=$(pwd -P)/../tfrpc/server:/root/tfrpc/server \
        --volume=$(pwd -P)/../yolov3-tf2:/root/yolov3-tf2 \
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
        --memory-swap=$POCKET_BE_MEM_SWAP \
        --volume $(pwd -P)/../applications/${APPDIR}/data:/data \
        --volume=$(pwd -P)/../tfrpc/server:/root/tfrpc/server \
        --volume=$(pwd -P)/../yolov3-tf2:/root/yolov3-tf2 \
        --volume=${BASEDIR}/../../resources/models:/models \
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
        --memory-swap=$POCKET_BE_MEM_SWAP \
        --volume $(pwd -P)/../applications/${APPDIR}/data:/data \
        --volume=$(pwd -P)/../tfrpc/server:/root/tfrpc/server \
        --volume=$(pwd -P)/../yolov3-tf2:/root/yolov3-tf2 \
        --volume=${BASEDIR}/../../resources/models:/models \
        $server_image \
        python tfrpc/server/yolo_server.py
}

function init() {
    docker rm -f $(docker ps -a | grep "grpc_server\|grpc_app_\|grpc_exp_server\|grpc_exp_app\|pocket\|monolithic" | awk '{print $1}') > /dev/null 2>&1
    docker container prune --force > /dev/null 2>&1

    if [[ ${#APPLICATIONS[@]} != 0 ]]; then
        APPLICATION=$(get_largest_app)
        APPDIR=$(get_application_dir $APPLICATION)
    fi

    mkdir -p ../applications/$APPDIR/data

    if [[ ! -f ../applications/$APPDIR/"${RESOURCE_CONFIG_FILE}".sh ]]; then
        # echo [W] config file ($APPDIR/"${RESOURCE_CONFIG_FILE}".sh) does not exist. Switching it back to the default one.
        echo [W] config file $APPDIR/"${RESOURCE_CONFIG_FILE}".sh does not exist. Switching it back to the default one.
        RESOURCE_CONFIG_FILE=resource_config
    fi

    if [[ ${#APPLICATIONS[@]} != 0 ]]; then
        local maxappnum=$(get_app_value $APPLICATION)
        echo app=$APPLICATION
        echo maxappnum=$maxappnum
        POCKET_BE_CPU=${POCKET_BE_CPU_PRESET[$maxappnum]}
        # POCKET_BE_MEM=${POCKET_BE_MEM_PRESET[$maxappnum]}
        POCKET_BE_MEM=$(get_max_be_mem)
        POCKET_BE_MEM_SWAP=$(bc <<< "$POCKET_BE_MEM * 4")
        POCKET_BE_MEM=${POCKET_BE_MEM}gb
        POCKET_BE_MEM_SWAP=${POCKET_BE_MEM_SWAP}gb

        POCKET_FE_CPU="To be defined in the experiment loop"
        POCKET_FE_MEM="To be defined in the experiment loop"
    else
        source ../applications/$APPDIR/"${RESOURCE_CONFIG_FILE}".sh $DEVICE
    fi

    if [[ ! -z $CPU_MULTIPLIER ]]; then
        POCKET_FE_CPU=$(bc <<< "$CPU_MULTIPLIER * $POCKET_FE_CPU")
        if [[ $POCKET_FE_CPU = "."* ]]; then
            POCKET_FE_CPU=0${POCKET_FE_CPU}
        fi
    fi

    echo DEVICE=$DEVICE
    echo POCKET_FE_CPU=$POCKET_FE_CPU
    echo POCKET_FE_MEM=$POCKET_FE_MEM
    echo POCKET_BE_CPU=$POCKET_BE_CPU
    echo POCKET_BE_MEM=$POCKET_BE_MEM
    echo POCKET_BE_MEM_SWAP=$POCKET_BE_MEM_SWAP
    echo MONOLITHIC_CPU=$MONOLITHIC_CPU
    echo MONOLITHIC_MEM=$MONOLITHIC_MEM

    # CC_POCKET_EXPERIMENT=$([[ $USER = "cc" ]] && echo 1 || echo 0)
    # if [[ $CC_POCKET_EXPERIMENT = "1" ]]; then
    #     CPUSET_CPUS=$(lscpu | grep -F "On-line CPU(s) list:" | cut -d' ' -f4)
    #     CPUSET_MEMS=$CPUSET_CPUS
    #     CPUSET_CPU_EXCLUSIVE=0
    #     CPUSET_MEM_EXCLUSIVE=0
    #     DOCKER_CPUS=$(lscpu | grep -F "NUMA node1 CPU(s):" | cut -d' ' -f4)
    #     # DOCKER_CPUS=0-47

    #     echo $DOCKER_CPUS | sudo tee /sys/fs/cgroup/cpuset/docker/cpuset.cpus
    #     echo $DOCKER_CPUS | sudo tee /sys/fs/cgroup/cpuset/docker/cpuset.mems
    #     echo 1 | sudo tee /sys/fs/cgroup/cpuset/docker/cpuset.cpu_exclusive
    #     echo 1 | sudo tee /sys/fs/cgroup/cpuset/docker/cpuset.mem_exclusive
    # fi


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
    cp -R ${BASEDIR}/../../resources/obj_det_sample_img ../applications/${APPDIR}/dockerfiles/${DEVICE}

    docker rmi -f pocket-${APPLICATION}-${DEVICE}-monolithic-perf
    docker image build --no-cache -t pocket-${APPLICATION}-${DEVICE}-monolithic-perf -f ../applications/${APPDIR}/dockerfiles/${DEVICE}/Dockerfile.monolithic.perf ../applications/${APPDIR}/dockerfiles/${DEVICE}

    docker rmi -f pocket-${APPLICATION}-${DEVICE}-monolithic-papi
    docker image build --no-cache -t pocket-${APPLICATION}-${DEVICE}-monolithic-papi -f ../applications/${APPDIR}/dockerfiles/${DEVICE}/Dockerfile.monolithic.papi ../applications/${APPDIR}/dockerfiles/${DEVICE}

    docker rmi -f pocket-${APPLICATION}-${DEVICE}-server
    docker image build -t pocket-${APPLICATION}-${DEVICE}-server -f ../applications/${APPDIR}/dockerfiles/${DEVICE}/Dockerfile.pocket.ser ../applications/${APPDIR}/dockerfiles/${DEVICE}

    docker rmi -f pocket-${APPLICATION}-${DEVICE}-application
    docker image build -t pocket-${APPLICATION}-${DEVICE}-application -f ../applications/${APPDIR}/dockerfiles/${DEVICE}/Dockerfile.pocket.app ../applications/${APPDIR}/dockerfiles/${DEVICE}

    docker rmi -f pocket-${APPLICATION}-${DEVICE}-perf-application
    docker image build --no-cache -t pocket-${APPLICATION}-${DEVICE}-perf-application -f ../applications/${APPDIR}/dockerfiles/${DEVICE}/Dockerfile.pocket.perf.app ../applications/${APPDIR}/dockerfiles/${DEVICE}

    docker rmi -f pocket-${APPLICATION}-${DEVICE}-monolithic
    docker image build -t pocket-${APPLICATION}-${DEVICE}-monolithic -f ../applications/${APPDIR}/dockerfiles/${DEVICE}/Dockerfile.monolithic.perf ../applications/${APPDIR}/dockerfiles/${DEVICE}

    docker rmi -f pocket-${DEVICE}-pypapi-server
    docker image build -t pocket-${DEVICE}-pypapi-server -f ../applications/${APPDIR}/dockerfiles/${DEVICE}/Dockerfile.pocket.papi.ser ../applications/${APPDIR}/dockerfiles/${DEVICE}

    rm -rf $(ls -1 ../applications/${APPDIR}/dockerfiles/${DEVICE} | grep -v Dockerfile)
    docker image prune
}

function measure_latency() {
    local numinstances=$1
    local server_container_name=pocket-server-001
    local server_image=pocket-${APPLICATION}-${DEVICE}-server

    init

    run_server_basic $server_container_name $SERVER_IP $server_image
    sleep 7

    ${POCKET} \
        run \
            -d \
            -b pocket-${APPLICATION}-${DEVICE}-application \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --cpus=5 \
            --memory=$(bc <<< '1024 * 2')mb \
            --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
            --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
            --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env POCKET_MEM_POLICY=func,ratio,0.8 \
            --env POCKET_CPU_POLICY=func,ratio,0.8 \
            --env CONTAINER_ID=pocket-client-0000 \
            --workdir="/root/${APPLICATION}" \
            -- python3 app.pocket.py

    sleep 5
    ${POCKET} \
        wait pocket-client-0000 > /dev/null 2>&1

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ${POCKET} \
            run \
                -d \
                -b pocket-${APPLICATION}-${DEVICE}-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --cpus=$POCKET_FE_CPU \
                --memory=$POCKET_FE_MEM \
                --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
                --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
                --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
                --env CONTAINER_ID=${container_name} \
                --workdir="/root/${APPLICATION}" \
                -- python3 app.pocket.py
        interval=$(generate_rand_num 3)
        sleep $interval
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        ${POCKET} \
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

    if [[ $RUSAGE_MEASURE -eq 1 ]]; then
        docker stop ${server_container_name} > /dev/null 2>&1
        docker wait ${server_container_name} > /dev/null 2>&1
        docker logs ${server_container_name} 2>&1 | grep -F "[resource_usage]"
        for i in $(seq 1 $numinstances); do
            local index=$(printf "%04d" $i)
            local container_name=pocket-client-${index}
            docker logs $container_name 2>&1 | grep -F "[resource_usage]"
        done
    fi
}

function measure_latency_varying_policy() {
    local numinstances=$1
    local server_container_name=pocket-server-001
    local server_image=pocket-${APPLICATION}-${DEVICE}-server

    init

    run_server_basic $server_container_name $SERVER_IP $server_image
    sleep 7

    ${POCKET} \
        run \
            -d \
            -b pocket-${APPLICATION}-${DEVICE}-application \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --cpus=5 \
            --memory=$(bc <<< '1024 * 2')mb \
            --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
            --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
            --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env POCKET_MEM_POLICY=func,ratio,0.8 \
            --env POCKET_CPU_POLICY=func,ratio,0.8 \
            --env CONTAINER_ID=pocket-client-0000 \
            --workdir="/root/${APPLICATION}" \
            -- python3 app.pocket.py

    sleep 5
    ${POCKET} \
        wait pocket-client-0000 > /dev/null 2>&1

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ${POCKET} \
            run \
                -d \
                -b pocket-${APPLICATION}-${DEVICE}-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --cpus=$POCKET_FE_CPU \
                --memory=$POCKET_FE_MEM \
                --oom-kill-disable \
                --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
                --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
                --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
                --env CONTAINER_ID=${container_name} \
                --workdir="/root/${APPLICATION}" \
                -- python3 app.pocket.varying_policy.py
        interval=$(generate_rand_num 3)
        sleep $interval
    done
# varying_policy
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        timeout 5m ${POCKET} \
            wait pocket-client-${index} > /dev/null 2>&1
        docker stop pocket-client-${index} > /dev/null 2>&1
    done

    # # For debugging
    # docker logs pocket-server-001
    # docker logs -f pocket-client-$(printf "%04d" $numinstances)

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker logs $container_name 2>&1 | grep "inference_time"
    done

    if [[ $RUSAGE_MEASURE -eq 1 ]]; then
        docker stop ${server_container_name} > /dev/null 2>&1
        docker wait ${server_container_name} > /dev/null 2>&1
        docker logs ${server_container_name} 2>&1 | grep -F "[resource_usage]"
        for i in $(seq 1 $numinstances); do
            local index=$(printf "%04d" $i)
            local container_name=pocket-client-${index}
            docker logs $container_name 2>&1 | grep -F "[resource_usage]"
        done
    fi
}

function mix() {
    local numinstances=$1
    local server_container_name=pocket-server-001
    local server_image=pocket-${APPLICATION}-${DEVICE}-server

    init

    run_server_basic $server_container_name $SERVER_IP $server_image
    sleep 7
    echo APPLICATIONS=\(${APPLICATIONS[@]}\)
    for app in ${APPLICATIONS[@]}; do
        local appdir="$(get_application_dir $app)"
        ${POCKET} \
            run \
                -d \
                -b pocket-${app}-${DEVICE}-application \
                -t pocket-client-${app}-0000 \
                -s ${server_container_name} \
                --cpus=5 \
                --memory=$(bc <<< '1024 * 2')mb \
                --volume=$(pwd -P)/../applications/${appdir}/data:/data \
                --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd -P)/../applications/${appdir}:/root/${app} \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env POCKET_MEM_POLICY=func,ratio,0.8 \
                --env POCKET_CPU_POLICY=func,ratio,0.8 \
                --env CONTAINER_ID=pocket-client-0000 \
                --workdir="/root/${app}" \
                -- python3 app.pocket.py

        sleep 5
        ${POCKET} \
            wait pocket-client-${app}-0000 > /dev/null 2>&1
    done

    for i in $(seq 1 $numinstances); do
        for app in ${APPLICATIONS[@]}; do
            local appdir="$(get_application_dir $app)"
            local index=$(printf "%04d" $i)
            local container_name=pocket-client-${app}-${index}
            local appnum="$(get_app_value $app)"

            ${POCKET} \
                run \
                    -d \
                    -b pocket-${app}-${DEVICE}-application \
                    -t ${container_name} \
                    -s ${server_container_name} \
                    --cpus=${POCKET_FE_CPU_PRESET[$appnum]} \
                    --memory=${POCKET_FE_MEM_PRESET[$appnum]}gb \
                    --volume=$(pwd -P)/../applications/${appdir}/data:/data \
                    --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
                    --volume=$(pwd -P)/../applications/${appdir}:/root/${app} \
                    --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                    --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                    --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                    --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
                    --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
                    --env CONTAINER_ID=${container_name} \
                    --workdir="/root/${app}" \
                    -- python3 app.pocket.py
            interval=$(generate_rand_num 3)
            sleep $interval
        done
    done

    for i in $(seq 1 $numinstances); do
        for app in ${APPLICATIONS[@]}; do
            local appdir="$(get_application_dir $app)"
            local index=$(printf "%04d" $i)
            ${POCKET} \
                wait pocket-client-${app}-${index} > /dev/null 2>&1
        done
    done

    # # For debugging
    # docker logs pocket-server-001
    # docker logs -f pocket-client-$(printf "%04d" $numinstances)

    for i in $(seq 1 $numinstances); do
        for app in ${APPLICATIONS[@]}; do
            local appdir="$(get_application_dir $app)"
            local index=$(printf "%04d" $i)
            local container_name=pocket-client-${app}-${index}
            docker logs $container_name 2>&1 | grep "inference_time"
        done
    done

    if [[ $RUSAGE_MEASURE -eq 1 ]]; then
        docker stop ${server_container_name} > /dev/null 2>&1
        docker wait ${server_container_name} > /dev/null 2>&1
        docker logs ${server_container_name} 2>&1 | grep -F "[resource_usage]"
        for i in $(seq 1 $numinstances); do
            for app in ${APPLICATIONS[@]}; do
                local appdir="$(get_application_dir $app)"
                local index=$(printf "%04d" $i)
                local container_name=pocket-client-${app}-${index}
                docker logs $container_name 2>&1 | grep -F "[resource_usage]"
            done
        done
    fi
}

function mix_monolithic() {
    local numinstances=$1

    init
    echo APPLICATIONS=\(${APPLICATIONS[@]}\)

    for i in $(seq 1 $numinstances); do
        for app in ${APPLICATIONS[@]}; do
            local appdir="$(get_application_dir $app)"
            local index=$(printf "%04d" $i)
            local container_name=${app}-monolithic-${index}
            local appnum="$(get_app_value $app)"

            eval docker \
                run \
                    -d "${GPUS}" \
                    --name ${container_name} \
                    --cpus=${MONOLITHIC_CPU_PRESET[$appnum]} \
                    --memory=${MONOLITHIC_MEM_PRESET[$appnum]}gb \
                    --volume=$(pwd -P)/../applications/${appdir}/data:/data \
                    --volume=$(pwd -P)/../applications/${appdir}:/root/${app} \
                    --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                    --volume=${BASEDIR}/../../resources/models:/models \
                    --workdir=/root/${app} \
                    pocket-${app}-${DEVICE}-monolithic \
                    python3 app.monolithic.py
                interval=$(generate_rand_num 3)
                sleep $interval
        done
    done

    for i in $(seq 1 $numinstances); do
        for app in ${APPLICATIONS[@]}; do
            local index=$(printf "%04d" $i)
            local container_name=${app}-monolithic-${index}

            docker wait "${container_name}" > /dev/null 2>&1
        done
    done

    # # For debugging
    # docker logs pocket-server-001
    # docker logs -f pocket-client-$(printf "%04d" $numinstances)

    for i in $(seq 1 $numinstances); do
        for app in ${APPLICATIONS[@]}; do
            local index=$(printf "%04d" $i)
            local container_name=${app}-monolithic-${index}
            docker logs $container_name 2>&1 | grep "inference_time"
        done
    done

    if [[ $RUSAGE_MEASURE -eq 1 ]]; then
        for i in $(seq 1 $numinstances); do
            for app in ${APPLICATIONS[@]}; do
                local index=$(printf "%04d" $i)
                local container_name=${app}-monolithic-${index}
                docker logs $container_name 2>&1 | grep -F "[resource_usage]"
            done
        done
    fi
}

function nop() {
    local numinstances=$1
    local server_container_name=pocket-server-001
    local server_image=pocket-mobilenetv2-${DEVICE}-server

    init

    run_server_nop $server_container_name $SERVER_IP $server_image
    sleep 7

    ${POCKET} \
        run \
            -d \
            -b pocket-mobilenetv2-${DEVICE}-application \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --cpus=5 \
            --memory=$(bc <<< '1024 * 2')mb \
            --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
            --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
            --volume=$(pwd -P)/../applications/${APPDIR}:/root/mobilenetv2 \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env POCKET_MEM_POLICY=func,ratio,0.8 \
            --env POCKET_CPU_POLICY=func,ratio,0.8 \
            --env CONTAINER_ID=pocket-client-0000 \
            --workdir="/root/mobilenetv2" \
            -- python3 app.pocket.nop.py

    sleep 3

    docker stop pocket-client-0000 > /dev/null 2>&1

    sleep 5
    ${POCKET} \
        wait pocket-client-0000 > /dev/null 2>&1

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ${POCKET} \
            run \
                -d \
                -b pocket-mobilenetv2-${DEVICE}-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --cpus=$POCKET_FE_CPU \
                --memory=$POCKET_FE_MEM \
                --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
                --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd -P)/../applications/${APPDIR}:/root/mobilenetv2 \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
                --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
                --env CONTAINER_ID=${container_name} \
                --workdir="/root/mobilenetv2" \
                -- python3 app.pocket.nop.py
        interval=$(generate_rand_num 3)
        sleep $interval
    done

    sleep $(bc <<< "$numinstances * 1.5")

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        docker stop pocket-client-${index} > /dev/null 2>&1
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        ${POCKET} \
            wait pocket-client-${index} > /dev/null 2>&1
    done

    # # For debugging
    # docker logs pocket-server-001
    # docker logs -f pocket-client-$(printf "%04d" $numinstances)

    if [[ $RUSAGE_MEASURE -eq 1 ]]; then
        docker stop ${server_container_name} > /dev/null 2>&1
        docker wait ${server_container_name} > /dev/null 2>&1
        docker logs ${server_container_name} 2>&1 | grep -F "[resource_usage]"
        for i in $(seq 1 $numinstances); do
            local index=$(printf "%04d" $i)
            local container_name=pocket-client-${index}
            docker logs $container_name 2>&1 | grep -F "[resource_usage]"
        done
    fi
}

function measure_exec_breakdown() {
    local numinstances=$1
    local server_container_name=pocket-server-001
    local server_image=pocket-${APPLICATION}-${DEVICE}-server

    init

    run_server_basic $server_container_name $SERVER_IP $server_image
    sleep 7

    ${POCKET} \
        run \
            -d \
            -b pocket-${APPLICATION}-${DEVICE}-application \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --cpus=5 \
            --memory=$(bc <<< '1024 * 2')mb \
            --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
            --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
            --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env POCKET_MEM_POLICY=func,ratio,0.8 \
            --env POCKET_CPU_POLICY=func,ratio,0.8 \
            --env CONTAINER_ID=pocket-client-0000 \
            --workdir="/root/${APPLICATION}" \
            -- python3 app.pocket.execbd.py

    sleep 5
	${POCKET} \
        wait pocket-client-0000 > /dev/null 2>&1

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ${POCKET} \
            run \
                -d \
                -b pocket-${APPLICATION}-${DEVICE}-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=$POCKET_FE_MEM \
                --cpus=$POCKET_FE_CPU \
                --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
                --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
                --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
                --env CONTAINER_ID=${container_name} \
                --workdir="/root/${APPLICATION}" \
                -- python3 app.pocket.execbd.py
        interval=$(generate_rand_num 3)
        sleep $interval
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        ${POCKET} \
            wait pocket-client-${index} > /dev/null 2>&1
    done

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

function evaluate_isolation() {
    local numinstances=$1
    local server_container_name=pocket-server-001
    local server_image=pocket-${APPLICATION}-${DEVICE}-server

    ## test namespace creation.
    init
    run_server_nop $server_container_name $SERVER_IP $server_image
    sleep 7

    local container_name=pocket-client-nscreation
    ${POCKET} \
        run \
            -d \
            -b pocket-mobilenetv2-${DEVICE}-application \
            -t ${container_name} \
            -s ${server_container_name} \
            --cpus=$POCKET_FE_CPU \
            --memory=$POCKET_FE_MEM \
            --volume=$(pwd -P)/../applications/mobilenetv2/data:/data \
            --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
            --volume=$(pwd -P)/../applications/mobilenetv2:/root/mobilenetv2 \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env POCKET_MEM_POLICY=func,ratio,0.8 \
            --env POCKET_CPU_POLICY=func,ratio,0.8 \
            --env CONTAINER_ID=${container_name} \
            --workdir="/root/mobilenetv2" \
            -- python3 app.pocket.nop.py
    sleep 3
    docker stop ${container_name} > /dev/null 2>&1
    sleep 5
    ${POCKET} \
        wait ${container_name} > /dev/null 2>&1

    docker logs ${container_name} | grep 'namespace_creation'


    # config: all, all off, all but ns, all but private queue, all but acl
    # local literal_config=(all_but_ns all_but_acls)
    # local actual_config=("pq,acl" "ns,pq")
    # for i in $(seq 0 1); do
    local literal_config=(all_on all_off all_but_ns all_but_pq all_but_acls)
    local actual_config=("ns,pq,acl" "" "pq,acl" "ns,acl" "ns,pq")
    for i in $(seq 0 4); do
        local isolation_config=${actual_config[i]}
        local nscreate=$([[ "$isolation_config" == *"ns"* ]] && echo on || echo off)
        local privatequeue=$([[ "$isolation_config" == *"pq"* ]] && echo on || echo off)
        local acl=$([[ "$isolation_config" == *"acl"* ]] && echo on || echo off)

        # echo misun nscreate=$nscreate privatequeue=$privatequeue acl=$acl

        init

        run_server_isolation_config $server_container_name $SERVER_IP $server_image $isolation_config
        sleep 7

        ${POCKET} \
            run \
                -d \
                -b pocket-${APPLICATION}-${DEVICE}-application \
                -t pocket-client-0000 \
                -s ${server_container_name} \
                --cpus=5 \
                --memory=$(bc <<< '1024 * 2')mb \
                --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
                --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env POCKET_MEM_POLICY=func,ratio,0.8 \
                --env POCKET_CPU_POLICY=func,ratio,0.8 \
                --env CONTAINER_ID=pocket-client-0000 \
                --env NSCREATE=$nscreate \
                --env PRIVATEQUEUE=$privatequeue \
                --env CAPABILITIESLIST=$acl \
                --workdir="/root/${APPLICATION}" \
                -- python3 app.pocket.py

        sleep 5
        ${POCKET} \
            wait pocket-client-0000 > /dev/null 2>&1
        # docker logs pocket-client-0000
        # docker logs pocket-server-001

        local container_name=pocket-client-${literal_config[$i]}

        ${POCKET} \
            run \
                -d \
                -b pocket-${APPLICATION}-${DEVICE}-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --cpus=$POCKET_FE_CPU \
                --memory=$POCKET_FE_MEM \
                --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
                --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
                --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
                --env CONTAINER_ID=${container_name} \
                --env NSCREATE=$nscreate \
                --env PRIVATEQUEUE=$privatequeue \
                --env CAPABILITIESLIST=$acl \
                --workdir="/root/${APPLICATION}" \
                -- python3 app.pocket.py
        sleep 5

        ${POCKET} \
            wait ${container_name} > /dev/null 2>&1
        local infer_time=$(docker logs ${container_name} 2>&1 | grep -F 'inference_time' | cut -d'=' -f2)
        # docker logs pocket-client-all_on
        # docker attach pocket-client-all_on
        docker rm -f ${container_name}
        
        ${POCKET} \
            run \
                -d \
                -b pocket-${APPLICATION}-${DEVICE}-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --cpus=$POCKET_FE_CPU \
                --memory=$POCKET_FE_MEM \
                --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
                --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
                --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
                --env CONTAINER_ID=${container_name} \
                --env NSCREATE=$nscreate \
                --env PRIVATEQUEUE=$privatequeue \
                --workdir="/root/${APPLICATION}" \
                -- python3 app.pocket.hello.py
        sleep 5

        ${POCKET} \
            wait ${container_name} > /dev/null 2>&1
        local null_rtt=$(docker logs ${container_name} 2>&1 | grep -F 'null_rtt' | cut -d'=' -f2)

        echo [isolation] ${literal_config[$i]} infer ${infer_time} null_rtt ${null_rtt}
    done
}

function evaluate_resource_amplification_null() {
    local numinstances=$1
    local server_container_name=pocket-server-001
    local server_image=pocket-${APPLICATION}-${DEVICE}-server

    init

    run_server_basic $server_container_name $SERVER_IP $server_image
    sleep 7

    # ${POCKET} \
    #     run \
    #         -d \
    #         -b pocket-${APPLICATION}-${DEVICE}-application \
    #         -t pocket-client-0000 \
    #         -s ${server_container_name} \
    #         --cpus=5 \
    #         --memory=$(bc <<< '1024 * 2')mb \
    #         --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
    #         --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
    #         --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
    #         --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
    #         --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
    #         --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
    #         --env POCKET_MEM_POLICY=func,ratio,0.8 \
    #         --env POCKET_CPU_POLICY=func,ratio,0.8 \
    #         --env CONTAINER_ID=pocket-client-0000 \
    #         --workdir="/root/${APPLICATION}" \
    #         -- python3 app.pocket.py

    # sleep 5
    # ${POCKET} \
    #     wait pocket-client-0000 > /dev/null 2>&1

    local pocket_fe_mem=$(echo "${POCKET_FE_MEM_PRESET[1]} * 1024 / 2.5" | bc)mb
    echo \<result\> ${POCKET_FE_MEM_PRESET[1]}
    echo \<result\> $pocket_fe_mem


    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ${POCKET} \
            run \
                -d \
                -b pocket-${APPLICATION}-${DEVICE}-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --cpus=$POCKET_FE_CPU \
                --memory=$pocket_fe_mem \
                --oom-kill-disable \
                --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
                --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
                --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
                --env CONTAINER_ID=${container_name} \
                --workdir="/root/${APPLICATION}" \
                -- python3 app.pocket.eval.resource.py
        interval=$(generate_rand_num 3)
        sleep $interval
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        ${POCKET} \
            wait pocket-client-${index} > /dev/null 2>&1
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker logs $container_name 2>&1 | grep -F '<result>'
    done

    # oomkiller turn off

    # sudo sh -c 'echo 1 > /sys/fs/cgroup/memory/docker/memory.oom_control'

    # fe_mem \= 10 # squeeze the memory

    # for i in $(seq $numinstances); do
    #     docker logs $pocket off | grep 'preprocessing_time'
    #     docker logs $static on | grep 'preprocessing_time'
    # done
    # for i in $(seq $numinstances); do
    #     docker logs $pocket off | grep 'inference_time'
    #     docker logs $static on | grep 'inference_time'
    # done
    # for i in $(seq $numinstances); do
    #     docker logs $pocket off | grep 'postprocessing_time'
    #     docker logs $static on | grep 'postprocessing_time'
    # done
}

function evaluate_resource_amplification() {
    local numinstances=$1
    local server_container_name=pocket-server-001
    local server_image=pocket-${APPLICATION}-${DEVICE}-server

    init

    run_server_basic $server_container_name $SERVER_IP $server_image
    sleep 7

    ${POCKET} \
        run \
            -d \
            -b pocket-${APPLICATION}-${DEVICE}-application \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --cpus=5 \
            --memory=$(bc <<< '1024 * 2')mb \
            --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
            --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
            --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env POCKET_MEM_POLICY=func,ratio,0.8 \
            --env POCKET_CPU_POLICY=func,ratio,0.8 \
            --env CONTAINER_ID=pocket-client-0000 \
            --workdir="/root/${APPLICATION}" \
            -- python3 app.pocket.py

    sleep 5
    ${POCKET} \
        wait pocket-client-0000 > /dev/null 2>&1

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ${POCKET} \
            run \
                -d \
                -b pocket-${APPLICATION}-${DEVICE}-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --cpus=$POCKET_FE_CPU \
                --memory=$POCKET_FE_MEM \
                --oom-kill-disable \
                --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
                --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
                --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
                --env CONTAINER_ID=${container_name} \
                --workdir="/root/${APPLICATION}" \
                -- python3 app.pocket.eval.resource.realapp.py
        interval=$(generate_rand_num 3)
        sleep $interval
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        ${POCKET} \
            wait pocket-client-${index} > /dev/null 2>&1
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker logs $container_name 2>&1 | grep -F '<result>'
    done

    # oomkiller turn off

    # sudo sh -c 'echo 1 > /sys/fs/cgroup/memory/docker/memory.oom_control'

    # fe_mem \= 10 # squeeze the memory

    # for i in $(seq $numinstances); do
    #     docker logs $pocket off | grep 'preprocessing_time'
    #     docker logs $static on | grep 'preprocessing_time'
    # done
    # for i in $(seq $numinstances); do
    #     docker logs $pocket off | grep 'inference_time'
    #     docker logs $static on | grep 'inference_time'
    # done
    # for i in $(seq $numinstances); do
    #     docker logs $pocket off | grep 'postprocessing_time'
    #     docker logs $static on | grep 'postprocessing_time'
    # done
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
        --name ${APPLICATION}-monolithic-0000 \
        --cpus=$MONOLITHIC_CPU \
        --memory=$MONOLITHIC_MEM \
        --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
        --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
        --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
        --volume=${BASEDIR}/../../resources/models:/models \
        --workdir=/root/${APPLICATION} \
        pocket-${APPLICATION}-${DEVICE}-monolithic \
        python3 app.monolithic.py >/dev/null 2>&1

    running_time=$(util_get_running_time ${APPLICATION}-monolithic-0000)
    echo $running_time > "${rusage_logging_dir}"/${APPLICATION}-monolithic-0000.latency

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=${APPLICATION}-monolithic-${index}

        eval docker \
            run \
                -d "${GPUS}" \
                --name ${container_name} \
                --cpus=$MONOLITHIC_CPU \
                --memory=$MONOLITHIC_MEM \
                --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
                --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --volume=${BASEDIR}/../../resources/models:/models \
                --workdir=/root/${APPLICATION} \
                pocket-${APPLICATION}-${DEVICE}-monolithic \
                python3 app.monolithic.py
        sleep $(generate_rand_num 3)
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=${APPLICATION}-monolithic-${index}

        docker wait "${container_name}"
        # running_time=$(util_get_running_time "${container_name}")
        # echo $running_time > "${rusage_logging_dir}"/"${container_name}".latency
        # echo $running_time
    done

    # local folder=$(realpath data/${TIMESTAMP}-${numinstances}-graph-monolithic)
    # mkdir -p $folder
    # for i in $(seq 0 $numinstances); do
    #     local index=$(printf "%04d" $i)
    #     local container_name=${APPLICATION}-monolithic-${index}
    #     docker logs $container_name 2>&1 | grep "graph_construction_time" > $folder/$container_name.graph
    # done

    # folder=$(realpath data/${TIMESTAMP}-${numinstances}-inf-monolithic)
    # mkdir -p $folder
    # for i in $(seq 0 $numinstances); do
    #     local index=$(printf "%04d" $i)
    #     local container_name=${APPLICATION}-monolithic-${index}
    #     docker logs $container_name 2>&1 | grep "inference_time" > $folder/$container_name.inf
    # done

    # # For debugging
    # docker logs -f ${APPLICATION}-monolithic-$(printf "%04d" $numinstances)

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=${APPLICATION}-monolithic-${index}
        docker logs $container_name 2>&1 | grep "inference_time"
    done

    if [[ $RUSAGE_MEASURE -eq 1 ]]; then
        for i in $(seq 1 $numinstances); do
            local index=$(printf "%04d" $i)
            local container_name=${APPLICATION}-monolithic-${index}
            docker logs $container_name 2>&1 | grep -F "[resource_usage]"
        done
    fi
}

function measure_papi() {
    local numinstances=$1
    local server_container_name=pocket-server-001
    local server_image=pocket-${DEVICE}-pypapi-server

    init

    run_server_papi $server_container_name $SERVER_IP $server_image
    sleep 3

    ${POCKET} \
        run \
            -d \
            -b pocket-${APPLICATION}-${DEVICE}-application \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --cpus=5 \
            --memory=$(bc <<< '1024 * 2')mb \
            --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
            --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
            --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
            --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
            --env CONTAINER_ID=pocket-client-0000 \
            --workdir="/root/${APPLICATION}" \
            -- python3 app.pocket.py

    sleep 5
	${POCKET} \
        wait pocket-client-0000 > /dev/null 2>&1


    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ${POCKET} \
            run \
                -d \
                -b pocket-${APPLICATION}-${DEVICE}-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --cpus=$POCKET_FE_CPU \
                --memory=$POCKET_FE_MEM \
                --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
                --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
                --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
                --env CONTAINER_ID=${container_name} \
                --workdir="/root/${APPLICATION}" \
                -- python3 app.pocket.py
        interval=$(generate_rand_num 3)
        echo interval $interval
        sleep $interval
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        ${POCKET} \
            wait pocket-client-${index} > /dev/null 2>&1
    done
}

function measure_pf() {
    local numinstances=$1
    local server_container_name=pocket-server-001
    local server_image=pocket-${APPLICATION}-${DEVICE}-server

    init

    run_server_pf $server_container_name $SERVER_IP $server_image
    sleep 3

    ${POCKET} \
        run \
            -d \
            -b pocket-${APPLICATION}-${DEVICE}-application \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --cpus=5 \
            --memory=$(bc <<< '1024 * 2')mb \
            --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
            --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
            --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
            --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
            --env CONTAINER_ID=pocket-client-0000 \
            --workdir="/root/${APPLICATION}" \
            -- python3 app.pocket.py

    sleep 5
	${POCKET} \
        wait pocket-client-0000 > /dev/null 2>&1


    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ${POCKET} \
            run \
                -d \
                -b pocket-${APPLICATION}-${DEVICE}-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --cpus=$POCKET_FE_CPU \
                --memory=$POCKET_FE_MEM \
                --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
                --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
                --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
                --env CONTAINER_ID=${container_name} \
                --workdir="/root/${APPLICATION}" \
                -- python3 app.pocket.py
        interval=$(generate_rand_num 3)
        sleep $interval
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        ${POCKET} \
            wait pocket-client-${index} > /dev/null 2>&1
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
    #     --name ${APPLICATION}-monolithic-0000 \
                # --cpus=2 \
                # --memory=$(bc <<< '1024 * 1.3')mb \
    #     --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
    #     --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
    #     --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
    #     --workdir=/root/${APPLICATION} \
    #     --cap-add CAP_SYS_ADMIN \
    #     --volume=$(pwd -P)/../tfrpc/server/papi:/papi \
    #     --env EVENTSET=$EVENTSET \
    #     --env NUM=$NUMINSTANCES \
    #     pocket-${APPLICATION}-${DEVICE}-monolithic-papi \
    #     python3 app.monolithic.papi.py

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=${APPLICATION}-monolithic-${index}

        eval docker \
            run \
                -d "${GPUS}" \
                --name ${container_name} \
                --cpus=$MONOLITHIC_CPU \
                --memory=$MONOLITHIC_MEM \
                --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
                --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --volume=${BASEDIR}/../../resources/models:/models \
                --workdir=/root/${APPLICATION} \
                --cap-add CAP_SYS_ADMIN \
                --volume=$(pwd -P)/../tfrpc/server/papi:/papi \
                --env EVENTSET=$EVENTSET \
                --env NUM=$NUMINSTANCES \
                pocket-${APPLICATION}-${DEVICE}-monolithic-papi \
                python3 app.monolithic.papi.py
        sleep $(generate_rand_num 3)
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=${APPLICATION}-monolithic-${index}

        docker wait "${container_name}"
    done

    sudo sh -c 'echo 3 >/proc/sys/kernel/perf_event_paranoid'


    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=${APPLICATION}-monolithic-${index}
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
    #     --name ${APPLICATION}-monolithic-0000 \
                # --cpus=2 \
                # --memory=$(bc <<< '1024 * 1.3')mb \
    #     --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
    #     --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
    #     --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
    #     --workdir=/root/${APPLICATION} \
    #     --env NUM=$NUMINSTANCES \
    #     pocket-${APPLICATION}-${DEVICE}-monolithic-papi \
    #     python3 app.monolithic.pf.py
    #     # --cap-add CAP_SYS_ADMIN \

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=${APPLICATION}-monolithic-${index}

        eval docker \
            run \
                -d "${GPUS}" \
                --name ${container_name} \
                --cpus=$MONOLITHIC_CPU \
                --memory=$MONOLITHIC_MEM \
                --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
                --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --volume=${BASEDIR}/../../resources/models:/models \
                --workdir=/root/${APPLICATION} \
                --env NUM=$NUMINSTANCES \
                pocket-${APPLICATION}-${DEVICE}-monolithic-papi \
                python3 app.monolithic.pf.py
        sleep $(generate_rand_num 3)
    done
    
    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=${APPLICATION}-monolithic-${index}

        docker wait "${container_name}"
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=${APPLICATION}-monolithic-${index}
        docker logs $container_name 2>&1 | grep "inference_time"
    done
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
            --name ${APPLICATION}-monolithic-0000 \
            --cpus=1 \
            --memory=512mb \
            --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
            --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --cap-add SYS_ADMIN \
            --cap-add IPC_LOCK \
            --workdir=/root/${APPLICATION} \
            pocket-${APPLICATION}-${DEVICE}-monolithic-perf \
            perf stat -e ${PERF_COUNTERS} -o /data/$TIMESTAMP-${numinstances}-perf-monolithic/${APPLICATION}-monolithic-0000.perf.log python3 app.monolithic.py

    docker \
        wait \
            ${APPLICATION}-monolithic-0000

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=${APPLICATION}-monolithic-${index}

        docker \
            run \
                -di \
                --name ${container_name} \
                --cpus=1 \
                --memory=512mb \
                --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
                --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --cap-add SYS_ADMIN \
                --cap-add IPC_LOCK \
                --workdir=/root/${APPLICATION} \
                pocket-${APPLICATION}-${DEVICE}-monolithic-perf \
                perf stat -e ${PERF_COUNTERS} -o /data/$TIMESTAMP-${numinstances}-perf-monolithic/${container_name}.perf.log python3 app.monolithic.py
        sleep $(generate_rand_num 3)
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=${APPLICATION}-monolithic-${index}

        docker \
            wait \
                ${container_name}
    done

    # For debugging
    # docker logs -f yolo-monolithic-$(printf "%04d" $numinstances)
}

function measure_cprofile() {
    local numinstances=$1
    local container_list=()
    local rusage_logging_dir=$(realpath data/${TIMESTAMP}-${numinstances}-cprofile)
    local rusage_logging_file=tmp-service.log

    local server_container_name=pocket-server-001
    local server_image=pocket-${APPLICATION}-${DEVICE}-server

    mkdir -p ${rusage_logging_dir}
    init
    run_server_cProfile $server_container_name $SERVER_IP $server_image $TIMESTAMP $numinstances

    ${POCKET} \
        run \
            --cprofile $rusage_logging_dir \
            -d \
            -b pocket-${APPLICATION}-${DEVICE}-application \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=512mb \
            --cpus=1 \
            --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
            --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
            --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env CONTAINER_ID=pocket-client-0000 \
            --workdir="/root/${APPLICATION}" \
            -- python3.6 -m cProfile -o /data/${TIMESTAMP}-${numinstances}-cprofile/pocket-client-0000.cprofile app.pocket.py

    ${POCKET} \
        wait \
        pocket-client-0000

    sleep 5

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ${POCKET} \
            run \
                --cprofile $rusage_logging_dir \
                -d \
                -b pocket-${APPLICATION}-${DEVICE}-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=512mb \
                --cpus=1 \
                --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
                --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env CONTAINER_ID=${container_name} \
                --workdir="/root/${APPLICATION}" \
                -- python3.6 -m cProfile -o /data/${TIMESTAMP}-${numinstances}-cprofile/${container_name}.cprofile app.pocket.py
        sleep $(generate_rand_num 3)
    done

    sudo bash -c "echo 1 > /proc/sys/kernel/nmi_watchdog"

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ${POCKET} \
            wait \
                ${container_name}
    done

    ${POCKET} \
        service \
            kill ${server_container_name} \

    sleep 3

    for filename in data/$TIMESTAMP-${numinstances}-cprofile/* ; do
        echo $filename
        if [[ "$filename" == *.cprofile ]]; then
            ../pocket/parseprof -f "$filename"
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
    local server_image=pocket-${APPLICATION}-${DEVICE}-server

    mkdir -p ${rusage_logging_dir}
    init
    sudo bash -c "echo 0 > /proc/sys/kernel/nmi_watchdog"

    # sudo python unix_multi_server.py &
    run_server_perf $server_container_name $SERVER_IP $server_image

    ${POCKET} \
        run \
            --perf $rusage_logging_dir \
            -d \
            -b pocket-${APPLICATION}-${DEVICE}-perf-application \
            -t pocket-client-0000 \
            -s ${server_container_name} \
            --memory=512mb \
            --cpus=1 \
            --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
                --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
            --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
            --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
            --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
            --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
            --env CONTAINER_ID=pocket-client-0000 \
            --workdir="/root/${APPLICATION}" \
            -- perf stat -e ${PERF_COUNTERS} -o /data/$TIMESTAMP-${numinstances}-perf/pocket-client-0000.perf.log python3.6 app.pocket.py

    sleep 5
    ${POCKET} \
        wait \
        pocket-client-0000

    sleep 5

    local perf_record_pid=$(sudo ${POCKET} \
        service \
        perf ${server_container_name} --dir ${rusage_logging_dir} --counters cpu-cycles,page-faults,minor-faults,major-faults,cache-misses,LLC-load-misses,LLC-store-misses,dTLB-load-misses,iTLB-load-misses)

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ${POCKET} \
            run \
                -d \
                --perf $rusage_logging_dir \
                -b pocket-${APPLICATION}-${DEVICE}-perf-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=512mb \
                --cpus=1 \
                --volume=$(pwd -P)/../applications/${APPDIR}/data:/data \
                --volume=$(pwd -P)/../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd -P)/../applications/${APPDIR}:/root/${APPLICATION} \
                --volume=${BASEDIR}/../../resources/coco/val2017:/root/coco2017 \
                --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env CONTAINER_ID=${container_name} \
                --workdir="/root/${APPLICATION}" \
                -- perf stat -e ${PERF_COUNTERS} -o /data/$TIMESTAMP-${numinstances}-perf/$container_name.perf.log python3.6 app.pocket.py
        sleep $(generate_rand_num 3)
    done

    sudo bash -c "echo 1 > /proc/sys/kernel/nmi_watchdog"

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ${POCKET} \
            wait \
                ${container_name}
    done
    sudo kill -s INT $perf_record_pid

    ${POCKET} \
        service \
            kill ${server_container_name} \

    sleep 3

    # For debugging
    docker logs ${server_container_name}
    docker logs -f pocket-client-$(printf "%04d" $numinstances)
}

function finalize() {
    if [[ $MULTISOCKET = "1" ]]; then
        echo $CPUSET_CPUS > /sys/fs/cgroup/cpuset/docker/cpuset.cpus
        echo $CPUSET_MEMS > /sys/fs/cgroup/cpuset/docker/cpuset.mems
        echo $CPUSET_CPU_EXCLUSIVE > /sys/fs/cgroup/cpuset/docker/cpuset.cpu_exclusive
        echo $CPUSET_MEM_EXCLUSIVE > /sys/fs/cgroup/cpuset/docker/cpuset.mem_exclusive
    fi
}

parse_arg ${@:2}
echo '>>>>>>>POCKET_MEM_POLICY=' $POCKET_MEM_POLICY
echo '>>>>>>>POCKET_CPU_POLICY=' $POCKET_CPU_POLICY
COMMAND=$1

case $COMMAND in
    build)
        build_docker_files
        ;;
    'nop')
        nop $NUMINSTANCES
        ;;
    'latency-mon')
        measure_latency_monolithic $NUMINSTANCES
        ;;
    'mix')
        mix $NUMINSTANCES
        ;;
    'mix-mon')
        mix_monolithic $NUMINSTANCES
        ;;
    'eval-iso')
        evaluate_isolation $NUMINSTANCES
        ;;
    'eval-rsrc-null')
        evaluate_resource_amplification_null $NUMINSTANCES
        ;;
    'eval-rsrc')
        evaluate_resource_amplification $NUMINSTANCES
        ;;
    'perf-mon')
        measure_perf_monolithic $NUMINSTANCES
        ;;
    'latency')
        measure_latency $NUMINSTANCES
        ;;
    'latency-varying-policy')
        measure_latency_varying_policy $NUMINSTANCES
        ;;
    'measure-exec')
        measure_exec_breakdown $NUMINSTANCES
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
    'help'|*)
        help
        ;;

esac

# finalize
