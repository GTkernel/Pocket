#!/bin/bash


function main() {
    local docker_grp=$(check_docker_access)

    if [[ "${docker_grp}" = "1" ]]; then # false
        print_error "Your current uid does not belong to docker group. You may not have installed docker yet or your group is not evaluated yet."
        exit 1
    fi

    # build_image a_mobilenetv2
    # build_image a_resnet50
    # build_image a_smallbert
    build_image a_talkingheads
    # build_image a_ssdmobilenetv2_320x320
    # build_image a_ssdresnet50v1_640x640
}

function build_image() {
    local app_name=$1
    local workding_dir=$(pwd)

    cd ../$app_name

    bash exp_script.sh build

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