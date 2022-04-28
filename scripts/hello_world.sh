#!/usr/bin/env bash

BASEDIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# APPLICATIONS=(mobilenetv2 resnet50 smallbert ssdmobilenetv2_320x320 ssdresnet50v1_640x640 talkingheads)
APPLICATIONS=(ssdresnet50v1_640x640)
# APPLICATIONS=(ssdmobilenetv2_320x320)
# todo: check if dependencies installed properly.

function main() {
    # hello_world_minimal
    # print_success minimal
    hello_world_all
    print_success all 
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
    cd $path
    bash exp_script.sh latency -n=1 --policy=1 --device=cpu
    cd -
}

function hello_world_all() {
    for app in "${APPLICATIONS[@]}"; do
        local path=$BASEDIR/../a_${app}
        cd $path
        bash exp_script.sh latency -n=1 --policy=1 --device=cpu
        cd -
        print_success $app
    done
}

main "$@"; exit