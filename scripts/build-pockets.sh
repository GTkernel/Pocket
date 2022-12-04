#!/bin/bash

HELLOWORLD=0
MOBILENET=0
RESNET=0
SMALLBERT=0
TALKINGHEADS=0
SSDMOBILENET=0
SSDRESNET=0

GPU=0

function main() {
    local docker_grp=$(check_docker_access)

    if [[ "${docker_grp}" = "1" ]]; then # false
        print_error "Your current uid does not belong to docker group. You may not have installed docker yet or your group is not evaluated yet."
        exit 1
    fi
    
    parse_arg "${@:1}"
    if [[ "$HELLOWORLD" = "1" ]]; then
        print_info "Hello World example with MobileNetV2"
        build_image mobilenetv2
    else
        [[ "$MOBILENET" = "1" ]] && build_image mobilenetv2
        [[ "$RESNET" = "1" ]] && build_image resnet50
        [[ "$SMALLBERT" = "1" ]] && build_image smallbert
        [[ "$TALKINGHEADS" = "1" ]] && build_image talkingheads
        [[ "$SSDMOBILENET" = "1" ]] && build_image ssdmobilenetv2_320x320
        [[ "$SSDRESNET" = "1" ]] && build_image ssdresnet50v1_640x640
    fi
}

function parse_arg() {
    for arg in $@; do
        case $arg in
            --all)
                MOBILENET=1
                RESNET=1
                SMALLBERT=1
                TALKINGHEADS=1
                SSDMOBILENET=1
                SSDRESNET=1
                ;;
            --gpu=*)
                GPU=${arg#*=}
                ;;
            --hello-world)
                HELLOWORLD=1
                ;;
            --mobilenet|--mobilenetv2)
                MOBILENET=1
                ;;
            --resnet|--resnet50)
                RESNET=1
                ;;
            --smallbert)
                SMALLBERT=1
                ;;
            --talkingheads)
                TALKINGHEADS=1
                ;;
            --ssdmobilnet|--ssdmobilenetv2)
                SSDMOBILENET=1
                ;;
            --ssdresnet|--ssdresnet50|--ssdresnet50v1)
                SSDRESNET=1
                ;;
            *)
                echo Invalid option: $arg
                ;;
        esac
    done
}

function build_image() {
    local app_name=$1
    local workding_dir=$(pwd)

    cd ../applications/$app_name

    bash exp_script.sh build --device=$([[ "${GPU}" = "1" ]] && echo gpu || echo cpu)

    cd $workding_dir
}

function check_docker_access() {
    local my_groups=("$(id -Gn)")
    
    for group in ${my_groups[@]}; do
        if [[ "${group}" = "docker" ]]; then
            echo 0; return # return true
        fi
    done
    echo 1; return # return false
}


_BOLD="\e[1m"
_DIM="\e[2m"
_RED="\e[31m"
_LYELLOW="\e[93m"
_LGREEN="\e[92m"
_LCYAN="\e[96m"
_LMAGENTA="\e[95m"
_RESET="\e[0m"


function print_error() {
    local message=$1
    echo -e "${_BOLD}${_RED}[ERROR]${_RESET} ${message}${_RESET}"

}

function print_warning() {
    local message=$1
    echo -e "${_BOLD}${_LYELLOW}[WARN]${_RESET} ${message}${_RESET}"

}

function print_info() {
    local message=$1
    echo -e "${_BOLD}${_LGREEN}[INFO]${_RESET} ${message}${_RESET}"

}

function print_debug() {
    local message=$1
    echo -e "${_BOLD}${_LCYAN}[DEBUG]${_RESET} ${message}${_RESET}"

}

main "$@"; exit