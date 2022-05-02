#!/usr/bin/env bash

SCRIPTDIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )/../scripts
SCRIPT=${SCRIPTDIR}/exp_script.sh
APPLICATIONS=(mobilenetv2 resnet50 ssdmobilenetv2 ssdresnet50v1 smallbert talkingheads)
NUMINSTANCES=2

mkdir -p "${SCRIPTDIR}"/tmp
trap "exit 0" TERM
export MAINPID=$$

DEVICE=cpu
MEASURE_POCKET=on
MEASURE_STATIC=on
MEASURE_STATIC_NONE=on
MEASURE_MONOLITHIC=on
ITERATION=1

function main() {
    parse_arg "${@:2}"
    local command=$1

    case $command in
        run)
            run
            ;;
        parse)
            parse
            ;;
        *)
            echo No such command: $command
            ;;
    esac
}

function parse_arg() {
    for arg in "$@"; do
        case $arg in
            -n=*|--num=*)
                NUMINSTANCES="${arg#*=}"
                ;;
            --help)
                help
                ;;
            --pocket=*)
                MEASURE_POCKET=${arg#*=}
                ;;
            --static=*)
                MEASURE_STATIC=${arg#*=}
                ;;
            --static-none=*)
                MEASURE_STATIC_NONE=${arg#*=}
                ;;
            --monolithic=*)
                MEASURE_MONOLITHIC=${arg#*=}
                ;;
            -i=*|--iteration=*)
                ITERATION=${arg#*=}
                ;;
            -d=*|--device=*)
                DEVICE=${arg#*=}
                ;;
            *)
                echo No such argument: ${arg}
                ;;
        esac
    done
}

function help() {
    echo "Here you can write some instructions"
    kill -s TERM $MAINPID
}

function run() {
    [[ $MEASURE_POCKET = "on" ]] && measure_pocket
    [[ $MEASURE_STATIC = "on" ]] && measure_static
    [[ $MEASURE_STATIC_NONE = "on" ]] && measure_static_none
    [[ $MEASURE_MONOLITHIC = "on" ]] && measure_monolithic
}

function parse() {
    help
}

function measure_pocket() {
    echo [NUMINSTANCES=$NUMINSTANCES]: pocket-dynamic
    for app in ${APPLICATIONS[@]}; do
        echo APPLICATION=$app
        for n in $(seq $NUMINSTANCES); do
            echo "    n=$n"
            for i in $(seq $ITERATION); do
                echo "        i=$i"
                bash ${SCRIPT} latency -n=$NUMINSTANCES --policy=1 --device=${DEVICE} --rusage -a=${app}
                echo
            done
            echo
        done
        echo
    done
    echo
}

function measure_static() {
    echo [NUMINSTANCES=$NUMINSTANCES]: pocket-static
    for app in ${APPLICATIONS[@]}; do
        echo APPLICATION=$app
        for n in $(seq $NUMINSTANCES); do
            echo "    n=$n"
            for i in $(seq $ITERATION); do
                echo "        i=$i"
                bash ${SCRIPT} latency -n=$NUMINSTANCES --policy=4 --device=${DEVICE} --rusage -a=${app}
                echo
            done
            echo
        done
        echo
    done
    echo
}

function measure_static_none() {
    for app in ${APPLICATIONS[@]}; do
        echo APPLICATION=$app
        for n in $(seq $NUMINSTANCES); do
            echo "    n=$n"
            for i in $(seq $ITERATION); do
                echo "        i=$i"
                bash ${SCRIPT} latency -n=$NUMINSTANCES --policy=3 --device=${DEVICE} --rusage -a=${app}
                echo
            done
            echo
        done
        echo
    done
    echo
}

function measure_monolithic() {
    echo [NUMINSTANCES=$NUMINSTANCES]: monolithic
    for app in ${APPLICATIONS[@]}; do
        echo APPLICATION=$app
        for n in $(seq $NUMINSTANCES); do
            echo "    n=$n"
            for i in $(seq $ITERATION); do
                echo "        i=$i"
                bash ${SCRIPT} latency-mon -n=$NUMINSTANCES --policy=3 --device=${DEVICE} --rusage -a=${app}
                echo
            done
            echo
        done
        echo
    done
    echo
}

main "$@"; exit