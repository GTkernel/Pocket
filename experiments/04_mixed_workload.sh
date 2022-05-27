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

WORKSET_01=(${APPLICATIONS[@]}) # all
WORKSET_02=(mobilenetv2 ssdmobilenetv2 smallbert) # lighter
WORKSET_03=(resnet50 ssdresnet50v1 talkingheads) # heavier

WORKSET_04=(mobilenetv2 resnet50) # heavier
WORKSET_05=(ssdmobilenetv2 ssdresnet50v1) # heavier
WORKSET_06=(smallbert talkingheads)

WORKSET_07=(smallbert ssdresnet50v1) # heavier
WORKSET_08=(ssdmobilenetv2 talkingheads) # heavier

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
            echo No such command: $command. Try either \'run\' or \'parse\'
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
    run_pocket
    run_monolithic
}

function run_pocket() {
    run_pocket_combination 01
    run_pocket_combination 02
    run_pocket_combination 03
    run_pocket_combination 04
    run_pocket_combination 05
    run_pocket_combination 06
    run_pocket_combination 07
    run_pocket_combination 08
}

function run_monolithic() {
    run_monolithic_combination 01
    run_monolithic_combination 02
    run_monolithic_combination 03
    run_monolithic_combination 04
    run_monolithic_combination 05
    run_monolithic_combination 06
    run_monolithic_combination 07
    run_monolithic_combination 08
}

function run_pocket_combination() {
    local workset_index=$1
    local workset=($(get_workset $workset_index))
    local reversed_workset=($(get_reversed_workset $workset_index))

    local numapplications=${#workset[@]}
    NUMINSTANCES=$(bc <<< "12 / $numapplications")

    for i in $(seq $ITERATION); do
        echo \(workset=${workset_index}, order=regular, platform=pocket, iteration=$i\)
        bash ${SCRIPT} mix -n=$NUMINSTANCES --policy=1 --rusage --device=${DEVICE} --apps="$(join_by , ${workset[@]})"
    done
    # for i in $(seq $ITERATION); do
    #     echo \(workset=${workset_index}, order=reversed, platform=pocket, iteration=$i\)
    #     bash ${SCRIPT} mix -n=$NUMINSTANCES --policy=1 --rusage --device=${DEVICE} --apps="$(join_by , ${reversed_workset[@]})"
    # done

}

function run_monolithic_combination() {
    local workset_index=$1
    local workset=($(get_workset $workset_index))
    local reversed_workset=($(get_reversed_workset $workset_index))

    local numapplications=${#workset[@]}
    NUMINSTANCES=$(bc <<< "12 / $numapplications")

    for i in $(seq $ITERATION); do
        echo \(workset=${workset_index}, order=regular, platform=monolithic, iteration=$i\)
        bash ${SCRIPT} mix-mon -n=$NUMINSTANCES --rusage --device=${DEVICE} --apps="$(join_by , ${workset[@]})"
    done
    # for i in $(seq $ITERATION); do
    #     echo \(workset=${workset_index}, order=reversed, platform=monolithic, iteration=$i\)
    #     bash ${SCRIPT} mix-mon -n=$NUMINSTANCES --rusage --device=${DEVICE} --apps="$(join_by , ${reversed_workset[@]})"
    # done
}

function get_workset() {
    local index=$1
    case $index in
        01)
            echo ${WORKSET_01[@]}
            ;;
        02)
            echo ${WORKSET_02[@]}
            ;;
        03)
            echo ${WORKSET_03[@]}
            ;;
        04)
            echo ${WORKSET_04[@]}
            ;;
        05)
            echo ${WORKSET_05[@]}
            ;;
        06)
            echo ${WORKSET_06[@]}
            ;;
        07)
            echo ${WORKSET_07[@]}
            ;;
        08)
            echo ${WORKSET_08[@]}
            ;;
        *)
            echo [E] Index out of bound.
            kill -s TERM $MAINPID
            ;;
    esac
}

function get_reversed_workset() {
    local index=$1
    local original_workset=()
    local reversed_workset=()
    case $index in
        01)
            original_workset=(${WORKSET_01[@]})
            ;;
        02)
            original_workset=(${WORKSET_02[@]})
            ;;
        03)
            original_workset=(${WORKSET_03[@]})
            ;;
        04)
            original_workset=(${WORKSET_04[@]})
            ;;
        05)
            original_workset=(${WORKSET_05[@]})
            ;;
        06)
            original_workset=(${WORKSET_06[@]})
            ;;
        07)
            original_workset=(${WORKSET_07[@]})
            ;;
        08)
            original_workset=(${WORKSET_08[@]})
            ;;
        *)
            echo [E] Index out of bound.
            kill -s TERM $MAINPID
            ;;
    esac

    local max_index=$(bc <<< "${#original_workset[@]} - 1")
    for i in $(seq $max_index -1 0); do
        local reversed_i=$(bc <<< "$max_index - $i")
        reversed_workset[$i]=${original_workset[$reversed_i]}
    done
    echo ${reversed_workset[@]}
}

# function join_by {
#   local d=${1-} f=${2-}
#   if shift 2; then
#     printf %s "$f" "${@/#/$d}"
#   fi
# }

function join_by { local IFS="$1"; shift; echo "$*"; }

function parse() {
    echo "Implement postprocessing the output"
}

main "$@"; echo \(DONE, time=$(date)\); exit