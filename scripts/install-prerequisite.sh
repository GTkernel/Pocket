#!/bin/bash


function main() {
    install_docker

    ask_reboot
}

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