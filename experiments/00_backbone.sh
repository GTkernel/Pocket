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
    echo "Implement run"
}

function parse() {
    echo "Implement postprocessing the output"
}

main "$@"; echo \(DONE, time=$(date)\); exit