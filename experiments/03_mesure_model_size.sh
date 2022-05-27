#!/usr/bin/env bash

SCRIPTDIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )/../scripts
SCRIPT=${SCRIPTDIR}/exp_script.sh
APPLICATIONS=(mobilenetv2 resnet50 ssdmobilenetv2 ssdresnet50v1 smallbert talkingheads)
NUMINSTANCES=1
DEVICE=cpu
ITERATION=1

mkdir -p "${SCRIPTDIR}"/tmp
trap "exit 0" TERM
export MAINPID=$$

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
    local nop_max_mem=0
    local tf_max_mem=0
    local app_max_mem=()

    for i in $(seq $ITERATION); do
        echo \($i\)
        nop_max_mem=$(bash ${SCRIPT} nop -n=$NUMINSTANCES --policy=1 --rusage --device=cpu --rusage -a=mobilenetv2 --tf-server=0 | grep -F "memory.max_usage" | head -1)
        tf_max_mem=$(bash ${SCRIPT} nop -n=$NUMINSTANCES --policy=1 --rusage --device=cpu --rusage -a=mobilenetv2 --tf-server=1 | grep -F "memory.max_usage" | head -1)

        for app in ${APPLICATIONS[@]}; do
            local max_mem="$(bash ${SCRIPT} latency -n=$NUMINSTANCES --policy=1 --rusage --device=cpu --rusage -a=${app} | grep -F "memory.max_usage" | head -1)"
            max_mem=${max_mem#*=}
            app_max_mem+=($max_mem)
        done

        echo nop_max_mem=${nop_max_mem#*=}
        echo tf_max_mem=${tf_max_mem#*=}

        for j in ${!APPLICATIONS[@]}; do
            echo ${APPLICATIONS[$j]}_max_mem=${app_max_mem[$j]}
        done
        echo
    done
}

function parse() {
    echo "Implement postprocessing the output"
}

main "$@"; echo \(DONE, time=$(date)\); exit