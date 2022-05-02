#!/usr/bin/env bash
BASEDIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# APPLICATIONS=(mobilenetv2)
# APPLICATIONS=(mobilenetv2 talkingheads)
APPLICATIONS=(mobilenetv2 resnet50 smallbert ssdmobilenetv2 ssdresnet50v1 talkingheads)
# todo: check if dependencies installed properly.
NUMINSTANCES=1
MONOLITHIC=0
RUSAGE=''

function main() {
    parse_arg "$@"
    # hello_world_minimal
    # print_success minimal
    hello_world_all
    print_success all 
}

function parse_arg() {
    for arg in "$@"; do
        case $arg in
            -n=*|--num=*)
                NUMINSTANCES="${arg#*=}"
                ;;
            --monolithic)
                MONOLITHIC=1
                ;;
            --rusage|--resource)
                RUSAGE="--rusage"
        esac
    done
}

function print_success() {
    local what_is_done=$1
    echo
    echo ======================================
    echo "        $what_is_done is done"
    echo ======================================
    echo
}

function hello_world_minimal() {
    local app=mobilenetv2
    local path=$BASEDIR/../a_${app}
    local suffix=$([[ $MONOLITHIC -eq 1 ]] && echo '-mon')
    cd $path 
    bash exp_script.sh latency${suffix} -n=$NUMINSTANCES --policy=1 --device=cpu
    cd ~-
}

function hello_world_all() {
    for app in "${APPLICATIONS[@]}"; do
        local path=$BASEDIR/../a_${app}
        local suffix=$([[ $MONOLITHIC -eq 1 ]] && echo '-mon')
        bash exp_script.sh latency${suffix} -n=$NUMINSTANCES --policy=1 --device=cpu ${RUSAGE} -a=${app}
        docker ps -a
        print_success $app
    done
}

function old_hello_world_all() {
    for app in "${APPLICATIONS[@]}"; do
        local path=$BASEDIR/../a_${app}
        local suffix=$([[ $MONOLITHIC -eq 1 ]] && echo '-mon')
        cd $path
        bash exp_script.sh latency${suffix} -n=$NUMINSTANCES --policy=1 --device=cpu ${RUSAGE}
        cd ~-
        docker ps -a
        print_success $app
    done
}

main "$@"; exit