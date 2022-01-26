#!/bin/bash


function main() {
    PWD=$(pwd)
    SCRIPTDIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
    COMMAND=$1


    if [[ "$PWD" != "$SCRIPTDIR" ]]; then
        print_error "This script needs to be launched in its own root directory!\nexit"
        exit 1
    fi

    case $COMMAND in
        install-prerequisite)
            ./install-prerequisite.sh
            ;;
        build-pockets)
            ./build-pockets.sh
            ;;
    esac
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