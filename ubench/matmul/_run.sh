#!/bin/bash

SERVER_IP=111.222.3.26
# POCKET_MEM_POLICY='func,none'      # (func/conn, ratio/minimum/none)
# POCKET_CPU_POLICY='func,none'      #
POCKET_MEM_POLICY='func,ratio,0.8'      # (func/conn, ratio/minimum/none)
POCKET_CPU_POLICY='func,ratio,0.8'      #
NUMINSTANCES=1
FEMEM=120

function main(){
    parse_arg ${@:1}
    echo '>>>>>>>POCKET_MEM_POLICY=' $POCKET_MEM_POLICY
    echo '>>>>>>>POCKET_CPU_POLICY=' $POCKET_CPU_POLICY

    # build_matmul_lib
    # run_pocket_app $NUMINSTANCES
    run_pocket_app_fixed $NUMINSTANCES $TOTAL_MEM
}

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
            --size=*)
                SIZE="${arg#*=}"
                ;;
            --total=*)
                TOTAL_MEM="${arg#*=}"
                ;;
            --file=*)
                MYFILE="${arg#*=}"
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
                    5)
                        POCKET_MEM_POLICY='conn,ratio,0.7'      # (func/conn, ratio/minimum/none)
                        POCKET_CPU_POLICY='func,ratio,0.8'      #
                        ;;
                esac
                ;;
        esac
    done
}

function run_pocket_be() {
    local server_container_name=$1
    local server_ip=$2
    local server_image=$3

    docker run \
        -d \
        --privileged \
        --name=$server_container_name \
        --workdir='/root' \
        --env YOLO_SERVER=1 \
        --ip=$server_ip \
        --ipc=shareable \
        --cpus=1 \
        --memory=$(bc <<< '200')mb \
        --volume $(pwd)/../../scripts/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
        --volume $(pwd)/data:/data \
        --volume=$(pwd)/../../scripts/sockets:/sockets \
        --volume=$(pwd)/../../tfrpc/server:/root/tfrpc/server \
        --volume=$(pwd)/../../yolov3-tf2:/root/yolov3-tf2 \
        --volume=/sys/fs/cgroup/:/cg \
        --volume=$(pwd)/../../r_resources/models:/models \
        $server_image \
        python tfrpc/server/yolo_server.py
}

function run_pocket_be2() {
    local server_container_name=$1
    local server_ip=$2
    local server_image=$3
    local total_mem=$4
    local numinstances=$5

    local be_mem=$(bc <<< "$total_mem - $numinstances * $FEMEM")

    docker run \
        -d \
        --privileged \
        --name=$server_container_name \
        --workdir='/root' \
        --env YOLO_SERVER=1 \
        --ip=$server_ip \
        --ipc=shareable \
        --cpus=1 \
        --memory="${be_mem}"mb \
        --volume $(pwd)/../../scripts/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
        --volume $(pwd)/data:/data \
        --volume=$(pwd)/../../scripts/sockets:/sockets \
        --volume=$(pwd)/../../tfrpc/server:/root/tfrpc/server \
        --volume=$(pwd)/../../yolov3-tf2:/root/yolov3-tf2 \
        --volume=/sys/fs/cgroup/:/cg \
        --volume=$(pwd)/../../r_resources/models:/models \
        $server_image \
        python tfrpc/server/yolo_server.py
}

function run_pocket_app_fixed() {
    local numinstances=$1
    local total_mem=$2
    local rusage_logging_dir=$(realpath data/latency)

    local server_container_name=pocket-server-001
    local server_image=pocket-mobilenet-server 

    mkdir -p ${rusage_logging_dir}
    init > /dev/null 2>&1

    run_pocket_be2 $server_container_name $SERVER_IP $server_image $total_mem $numinstances > /dev/null
    sleep 3

    # ../../scripts/pocket/pocket \
    #     run \
    #         --measure-latency $rusage_logging_dir \
    #         -d \
    #         -b pocket-mobilenet-application \
    #         -t pocket-client-0000 \
    #         -s ${server_container_name} \
    #         --memory=2048mb \
    #         --cpus=5 \
    #         --volume=$(pwd)/data:/data \
    #         --volume $(pwd)/../scripts/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
    #         --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
    #         --volume=$(pwd):/root/mobilenet \
    #         --volume="$(pwd -P)"/../r_resources/coco/val2017:/root/coco2017 \
    #         --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
    #         --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
    #         --env POCKET_MEM_POLICY=func,ratio,0.8 \
    #         --env POCKET_CPU_POLICY=func,ratio,0.8 \
    #         --env CONTAINER_ID=pocket-client-0000 \
    #         --workdir='/root/mobilenet' \
    #         -- python3 app.pocket.py

    # sleep 5


    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ../../scripts/pocket/pocket \
            run \
                --measure-latency $rusage_logging_dir \
                -d \
                -b pocket-mobilenet-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=$(bc <<< "$FEMEM")mb \
                --cpus=1 \
                --volume=$(pwd)/data:/data \
                --volume $(pwd)/../../scripts/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=$(pwd)/../../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd):/root/mobilenet \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
                --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
                --env CONTAINER_ID=${container_name} \
                --workdir='/root/mobilenet' \
                -- python3 pocket.matmul.py $SIZE > /dev/null 2>&1 &
        interval=$(generate_rand_num 3)
        # echo interval $interval
        # sleep $interval
        sleep 1.5
    done

    sleep $(bc <<< "3 * $numinstances")

    # if [ "$( docker container inspect -f '{{.State.Running}}' $server_container_name )" != "true" ]; then 
    #     echo
    #     echo '==================================================================='
    #     echo '>>>>>>>' policy=$POLICY_NO, n==$numinstances, not okay
    #     exit
    #     # read
    # fi

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        # ret_val=$(docker wait $container_name)
        # if [[ "$ret_val" != "0" ]]; then
        #     echo
        #     echo '==================================================================='
        #     echo '>>>>>>>' policy=$POLICY_NO, n==$numinstances, not okay
        #     exit
        # fi
        while [[ "$( docker container inspect -f '{{.State.Status}}' $container_name )" = "created" && "$(docker container inspect -f '{{.State.Running}}' $server_container_name )" = "true"  ]]; do
            sleep 1
        done
    done

    sleep $(bc <<< "2 * $numinstances")

    # for i in $(seq 1 $numinstances); do
    #     local index=$(printf "%04d" $i)
    #     local container_name=pocket-client-${index}
    #     docker logs $container_name 2>&1 | grep "matmultest"
    # done
    # echo n==$numinstances, okay
    # run_pocket_app_fixed $(bc <<< "$numinstances + 1") $total_mem

    if [ "$( docker container inspect -f '{{.State.Running}}' $server_container_name )" != "true" ]; then 
        echo
        echo '==================================================================='
        echo '>>>>>>>' policy=$POLICY_NO, n==$numinstances, not okay, press enter
        # read
        echo $(bc <<< "$numinstances - 1") > $MYFILE
    else
        echo $numinstances > $MYFILE
        echo n==$numinstances, okay
        run_pocket_app_fixed $(bc <<< "$numinstances + 1") $total_mem
        # docker rm -f $(docker ps -aq) > /dev/null 2>&1
    fi

}

function run_pocket_app() {
    local numinstances=$1
    local rusage_logging_dir=$(realpath data/latency)

    local server_container_name=pocket-server-001
    local server_image=pocket-mobilenet-server 

    mkdir -p ${rusage_logging_dir}
    init

    run_pocket_be $server_container_name $SERVER_IP $server_image
    sleep 3

    # ../../scripts/pocket/pocket \
    #     run \
    #         --measure-latency $rusage_logging_dir \
    #         -d \
    #         -b pocket-mobilenet-application \
    #         -t pocket-client-0000 \
    #         -s ${server_container_name} \
    #         --memory=2048mb \
    #         --cpus=5 \
    #         --volume=$(pwd)/data:/data \
    #         --volume $(pwd)/../scripts/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
    #         --volume=$(pwd)/../tfrpc/client:/root/tfrpc/client \
    #         --volume=$(pwd):/root/mobilenet \
    #         --volume="$(pwd -P)"/../r_resources/coco/val2017:/root/coco2017 \
    #         --env RSRC_REALLOC_RATIO=${RSRC_RATIO} \
    #         --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
    #         --env POCKET_MEM_POLICY=func,ratio,0.8 \
    #         --env POCKET_CPU_POLICY=func,ratio,0.8 \
    #         --env CONTAINER_ID=pocket-client-0000 \
    #         --workdir='/root/mobilenet' \
    #         -- python3 app.pocket.py

    # sleep 5


    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}

        ../../scripts/pocket/pocket \
            run \
                --measure-latency $rusage_logging_dir \
                -d \
                -b pocket-mobilenet-application \
                -t ${container_name} \
                -s ${server_container_name} \
                --memory=$(bc <<< '100')mb \
                --cpus=1 \
                --volume=$(pwd)/data:/data \
                --volume $(pwd)/../../scripts/pocket/tmp/pocketd.sock:/tmp/pocketd.sock \
                --volume=$(pwd)/../../tfrpc/client:/root/tfrpc/client \
                --volume=$(pwd):/root/mobilenet \
                --env RSRC_REALLOC_ON=${RSRC_REALLOC} \
                --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
                --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
                --env CONTAINER_ID=${container_name} \
                --workdir='/root/mobilenet' \
                -- python3 pocket.matmul.py $SIZE &
        interval=$(generate_rand_num 3)
        # echo interval $interval
        sleep $interval
    done

    wait

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker wait $container_name
    done

    for i in $(seq 1 $numinstances); do
        local index=$(printf "%04d" $i)
        local container_name=pocket-client-${index}
        docker logs $container_name 2>&1 | grep "matmultest"
    done
}

function build_matmul_lib() {
    local cwd=$(pwd)

    local script_dir="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
    cd $script_dir/../../tfrpc/server/test
    make clean
    make

    cd $cwd
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

function init() {
    docker rm -f $(docker ps -a | grep "grpc_server\|grpc_app_\|grpc_exp_server\|grpc_exp_app\|pocket\|monolithic" | awk '{print $1}') > /dev/null 2>&1
    docker container prune --force
    sleep 3
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

main "$@"; exit