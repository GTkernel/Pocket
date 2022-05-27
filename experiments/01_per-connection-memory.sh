#!/usr/bin/env bash

SCRIPTDIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )/../scripts
SCRIPT=${SCRIPTDIR}/exp_script.sh
APPLICATIONS=(mobilenetv2 resnet50 ssdmobilenetv2 ssdresnet50v1 smallbert talkingheads)
NUMINSTANCES=2

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
            *)
                echo No such argument: ${arg}
                ;;
        esac
    done
}

function help() {
    echo "Output Parsing: grep 'max_memory' ../tmp/01-20220501.log | cut -d'=' -f2"
    kill -s TERM $MAINPID
}

function run() {
    parse_arg "$@"
    echo NOOP
    app=mobilenetv2
    max_memory_sum=0
    echo '    'APPLICATION=${app}
    for i in $(seq 1 $NUMINSTANCES); do
        echo '    ''    'NUMINSTANCES=$i
        local max_memory=$(bash ${SCRIPT} nop -n=$i --policy=1 --device=cpu --rusage -a=$app --tf-server=0 | grep -F "memory.max_usage" | head -1)
        echo '    ''    ''    'max_memory=${max_memory##*=}
        # max_memory_sum+=max_memory
    done
    echo

    echo
    
    echo OP
    for app in "${APPLICATIONS[@]}"; do
        max_memory_sum=0
        echo '    'APPLICATION=${app}
        for i in $(seq 1 $NUMINSTANCES); do
            echo '    ''    'NUMINSTANCES=$i
            local max_memory=$(bash ${SCRIPT} latency -n=$i --policy=1 --device=cpu --rusage -a=$app | grep -F "memory.max_usage" | head -1)
            echo '    ''    ''    'max_memory=${max_memory##*=}
            # max_memory_sum+=max_memory
        done
        echo
    done
}

function parse() {
    echo "Implement postprocessing the output"
}

main "$@"; echo \(DONE, time=$(date)\); exit