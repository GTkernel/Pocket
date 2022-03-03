#!/bin/bash


function main() {
    GPU=0
    SCRIPT_DIR="$(cd `dirname $0` > /dev/null && pwd -P)"

    if [ -z "$BASH" ]; then 
        print_error "Please run this script $0 with bash"
        exit 1
    fi

    if [[ "$(id -u)" -ne 0 ]]; then
        print_error "Please run this script with root privilege."
        exit 1
    fi

    if [[ "$SCRIPT_DIR" != "$(pwd -P)" ]]; then
        print_error "Please run this script in $(dirname $0)."
        exit 1
    fi

    parse_arg "${@:1}"
    
    install_packages
    download_coco_imageset
    install_docker
    if [[ "$GPU" = "0" ]]; then
        :
    else
        install_nvidia_driver
        install_nvidia_docker
    fi
    update_grub
    ask_reboot

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

function install_packages() {
    apt-get update -y
    apt-get install -y bc
    apt-get install gawk
}

function download_coco_imageset() {
    wget http://images.cocodataset.org/zips/val2017.zip
    mkdir -p ../r_resources/coco
    unzip val2017.zip -d ../r_resources/coco
    rm -f val2017.zip
}

# reboot required
function install_docker() {
    apt-get update -y

    # Download dependencies
    apt-get install -y apt-transport-https ca-certificates curl software-properties-common
    # Add Docker's GPG Key
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
    # Install the Docker Repository
    add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu  $(lsb_release -cs)  stable" 
    
    apt-get update
    apt-get install -y docker-ce=5:20.10.8~3-0~ubuntu-bionic

    # Post-installation steps
    groupadd docker
    usermod -aG docker $USER

    systemctl enable docker.service
    systemctl enable containerd.service
}

# reboot required
function install_nvidia_driver() {
    apt-get install linux-headers-$(uname -r) -y
    apt install ubuntu-drivers-common
    ubuntu-drivers devices
    ubuntu-drivers autoinstall
}

function install_nvidia_docker() {
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
        && curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add - \
        && curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | tee /etc/apt/sources.list.d/nvidia-docker.list
    apt-get update -y
    apt-get install nvidia-docker2 -y
    systemctl restart docker
    # docker run --gpus all -it --rm tensorflow/tensorflow:latest-gpu    nvidia-smi
}

function update_grub() {
    sed -i 's/cgroup_enable=memory swapaccount=1//' /etc/default/grub
    sed -i 's/GRUB_CMDLINE_LINUX="[^"]*/& cgroup_enable=memory swapaccount=1/' /etc/default/grub
    update-grub
}


function ask_reboot() {
    print_info "Prerequisite installation is complete and now the machine needs to reboot to run Pocket properly. Do you wish to reboot now?"
    select yn in "Yes" "No"; do
        case $yn in
             Yes) 
                reboot
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