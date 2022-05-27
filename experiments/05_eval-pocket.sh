#!/usr/bin/env bash

SCRIPTDIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )/../scripts
SCRIPT=${SCRIPTDIR}/exp_script.sh
APPLICATIONS=(mobilenetv2 resnet50 ssdmobilenetv2 ssdresnet50v1)
# APPLICATIONS=(mobilenetv2 resnet50 ssdmobilenetv2 ssdresnet50v1 smallbert talkingheads)
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
    evaluate_isolation
    # evaluate_resource_amplification
}

function evaluate_isolation() {
    for app in ${APPLICATIONS[@]}; do
        for i in $(seq $ITERATION); do
            echo \(testcase=evaluate_isolation, app=$app, iteration=$i\)
            # bash ${SCRIPT} eval-iso -n=$NUMINSTANCES --policy=1 --rusage --device=${DEVICE} -a=$app
            bash ${SCRIPT} eval-iso -n=$NUMINSTANCES --policy=1 --rusage --device=${DEVICE} -a=$app | grep -F [isolation]
        done
    done
}

function evaluate_resource_amplification() {
    echo \(testcase=resource_amplification, policy=dynamic, app=null\)
    for i in $(seq $ITERATION); do
        bash ${SCRIPT} eval-rsrc-null -n=$NUMINSTANCES --policy=1 --rusage --device=${DEVICE} -a=mobilenetv2 | grep -F '<result>'
    done
    for app in ${APPLICATIONS[@]}; do
        echo \(testcase=resource_amplification, policy=dynamic, app=$app\)
        for i in $(seq $ITERATION); do
            bash ${SCRIPT} eval-rsrc -n=$NUMINSTANCES --policy=1 --rusage --device=${DEVICE} -a=$app  | grep -F '<result>'
        done
    done
    echo \(testcase=resource_amplification, policy=static, app=null\)
    for i in $(seq $ITERATION); do
        bash ${SCRIPT} eval-rsrc-null -n=$NUMINSTANCES --policy=3 --rusage --device=${DEVICE} -a=mobilenetv2 | grep -F '<result>'
    done
    for app in ${APPLICATIONS[@]}; do
        echo \(testcase=resource_amplification, policy=static, app=$app\)
        for i in $(seq $ITERATION); do
            bash ${SCRIPT} eval-rsrc -n=$NUMINSTANCES --policy=3 --rusage --device=${DEVICE} -a=$app | grep -F '<result>'
        done
    done
}

function parse() {
    echo "Implement postprocessing the output"
}

main "$@"; echo \(DONE, time=$(date)\); exit