#!/bin/bash


function main() {
    GPU=0


    parse_arg "${@:1}"

    if [[ "$GPU" = "0" ]]; then
        install_docker
        ask_reboot
    else
        # install_docker
        install_nvidia_driver
        install_nvidia_docker
        ask_reboot
    fi

}

function parse_arg() {
    for arg in $@; do
        case $arg in
            --gpu=*)
                GPU=${arg#*=}
                ;;
        esac
    done
}

# reboot required
function install_docker() {
    sudo apt-get update -y

    # Download dependencies
    sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common
    # Add Docker's GPG Key
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
    # Install the Docker Repository
    sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu  $(lsb_release -cs)  stable" 
    
    sudo apt-get update
    sudo apt-get install -y docker-ce=5:20.10.8~3-0~ubuntu-bionic

    # Post-installation steps
    sudo groupadd docker
    sudo usermod -aG docker $USER

    sudo systemctl enable docker.service
    sudo systemctl enable containerd.service
}

# reboot required
function install_nvidia_driver() {
    sudo apt-get install linux-headers-$(uname -r) -y
    sudo apt install ubuntu-drivers-common
    ubuntu-drivers devices
    sudo ubuntu-drivers autoinstall
}

function install_nvidia_docker() {
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
        && curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add - \
        && curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
    sudo apt-get update -y
    sudo apt-get install nvidia-docker2 -y
    sudo systemctl restart docker
    # docker run --gpus all -it --rm tensorflow/tensorflow:latest-gpu    nvidia-smi
}


function ask_reboot() {
    print_info "Prerequisite installation is complete and now the machine needs to reboot to run Pocket properly. Do you wish to reboot now?"
    select yn in "Yes" "No"; do
        case $yn in
             Yes) 
                sudo reboot
                exit
                ;;
             No) 
                print_info "Reboot is required for you to run Pocket properly."
                exit
                ;;
        esac
    done
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