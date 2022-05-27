#!/usr/bin/env bash

SCRIPTDIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )/../scripts
SCRIPT=${SCRIPTDIR}/exp_script.sh
APPLICATIONS=(mobilenetv2 resnet50 ssdmobilenetv2 ssdresnet50v1 smallbert talkingheads)
NUMINSTANCES=2
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
    # for app in ${APPLICATIONS[@]}; do
    #     # local portion=$([[ $app = "ssd"* ]] && echo 8 || echo 9)
    #     for p in $(seq $portion); do
    #         echo \(testcase=varying_proportion, policy=dynamic, proportion=0.$p application=$app, total_iteration=$ITERATION\)
    #         local values=()
    #         for i in $(seq $ITERATION); do
    #             # bash ${SCRIPT} latency-varying-policy -n=1 --rusage --mempolicy="func,ratio,0.$p" --cpupolicy="func,ratio,0.$p" --cpu-multiplier=0.5 --device=${DEVICE} -a=$app
    #             local value=$(bash ${SCRIPT} latency-varying-policy -n=1 --rusage --mempolicy="func,ratio,0.$p" --cpupolicy="func,ratio,0.$p" --device=${DEVICE} -a=$app | grep -F 'inference_time' | cut -d'=' -f2)
    #             values+=($value)
    #         done
    #         for value in ${values[@]}; do
    #             echo $value
    #         done
    #         echo
    #     done
    # done

    # for app in ${APPLICATIONS[@]}; do
    #     local portion=$([[ $app = "ssd"* ]] && echo 8 || echo 9)
    #     for p in $(seq $portion); do
    #         echo \(testcase=varying_proportion, policy=static, proportion=0.$p application=$app, total_iteration=$ITERATION\)
    #         local values=()
    #         for i in $(seq $ITERATION); do
    #             # bash ${SCRIPT} latency-varying-policy -n=1 --rusage --mempolicy="conn,ratio,0.$p" --cpupolicy="conn,ratio,0.$p" --cpu-multiplier=0.5 --device=${DEVICE} -a=$app | grep -F 'inference_time' | cut -d'=' -f2
    #             local value=$(bash ${SCRIPT} latency-varying-policy -n=1 --rusage --mempolicy="conn,ratio,0.$p" --cpupolicy="conn,ratio,0.$p" --device=${DEVICE} -a=$app | grep -F 'inference_time' | cut -d'=' -f2)
    #             values+=($value)
    #         done
    #         for value in ${values[@]}; do
    #             echo $value
    #         done
    #         echo
    #     done
    # done

    local applications=(ssdmobilenetv2 ssdresnet50v1)
    applications=(mobilenetv2 resnet50 ssdmobilenetv2 ssdresnet50v1 smallbert talkingheads)

    for app in ${applications[@]}; do
        p=9
        p=0
        echo \(testcase=varying_proportion, policy=dynamic, proportion=0.$p application=$app, total_iteration=$ITERATION\)
        local values=()
        for i in $(seq $ITERATION); do
            # bash ${SCRIPT} latency-varying-policy -n=1 --rusage --mempolicy="func,ratio,0.$p" --cpupolicy="func,ratio,0.$p" --cpu-multiplier=0.5 --device=${DEVICE} -a=$app
            local value=$(bash ${SCRIPT} latency-varying-policy -n=1 --rusage --mempolicy="func,ratio,0.$p" --cpupolicy="func,ratio,0.$p" --device=${DEVICE} -a=$app | grep -F 'inference_time' | cut -d'=' -f2)
            values+=($value)
        done
        for value in ${values[@]}; do
            echo $value
        done
        echo
    done

    for app in ${applications[@]}; do
        local portion=$([[ $app = "ssd"* ]] && echo 8 || echo 9)
        p=9
        p=0
        echo \(testcase=varying_proportion, policy=static, proportion=0.$p application=$app, total_iteration=$ITERATION\)
        local values=()
        for i in $(seq $ITERATION); do
            # bash ${SCRIPT} latency-varying-policy -n=1 --rusage --mempolicy="conn,ratio,0.$p" --cpupolicy="conn,ratio,0.$p" --cpu-multiplier=0.5 --device=${DEVICE} -a=$app | grep -F 'inference_time' | cut -d'=' -f2
            local value=$(bash ${SCRIPT} latency-varying-policy -n=1 --rusage --mempolicy="conn,ratio,0.$p" --cpupolicy="conn,ratio,0.$p" --device=${DEVICE} -a=$app | grep -F 'inference_time' | cut -d'=' -f2)
            values+=($value)
        done
        for value in ${values[@]}; do
            echo $value
        done
        echo
    done
}

function parse() {
    echo "Implement postprocessing the output"
}

main "$@"; echo \(DONE, time=$(date)\); exit