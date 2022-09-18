#!/usr/bin/env bash


function main( ){
    print_info "Setting FireCracker.."
    print_info "Setting up KVM access.."
    sudo setfacl -m u:${USER}:rw /dev/kvm
    [ -r /dev/kvm ] && [ -w /dev/kvm ] && echo "KVM Access OK" || echo "KVM Access FAIL"
    
    print_info "Getting the FireCracker Binary.."
    release_url="https://github.com/firecracker-microvm/firecracker/releases"
    # latest=$(basename $(curl -fsSLI -o /dev/null -w  %{url_effective} ${release_url}/latest))
    version=v1.1.0
    arch=`uname -m`
    curl -L ${release_url}/download/${version}/firecracker-${version}-${arch}.tgz | tar -xz
    mv release-${version}-$(uname -m)/firecracker-${version}-$(uname -m) firecracker

    getting_default_kernel_fs
    # custom_rootfs_and_kernel    
}

function getting_default_kernel_fs() {
    print_info "Getting the kernel and rootfs.."
    arch=`uname -m`
    dest_kernel="hello-vmlinux.bin"
    dest_rootfs="hello-rootfs.ext4"
    image_bucket_url="https://s3.amazonaws.com/spec.ccfc.min/img/quickstart_guide/$arch"

    if [ ${arch} = "x86_64" ]; then
        kernel="${image_bucket_url}/kernels/vmlinux.bin"
        rootfs="${image_bucket_url}/rootfs/bionic.rootfs.ext4"
    elif [ ${arch} = "aarch64" ]; then
        kernel="${image_bucket_url}/kernels/vmlinux.bin"
        rootfs="${image_bucket_url}/rootfs/bionic.rootfs.ext4"
    else
        echo "Cannot run firecracker on $arch architecture!"
        exit 1
    fi

    echo "Downloading $kernel..."
    curl -fsSL -o $dest_kernel $kernel

    echo "Downloading $rootfs..."
    curl -fsSL -o $dest_rootfs $rootfs

    echo "Saved kernel file to $dest_kernel and root block device to $dest_rootfs."

}

function custom_rootfs_and_kernel() {
    # https://github.com/firecracker-microvm/firecracker/blob/main/docs/rootfs-and-kernel-setup.md
    # https://stackoverflow.com/questions/53938944/firecracker-microvm-how-to-create-custom-firecracker-microvm-and-file-system-im
    # https://gruchalski.com/posts/2021-03-23-introducing-firebuild/

    print_info "Build the rootfs using Firebuild.."
    print_info "Prerequisite: Install Go refer to https://go.dev/doc/install"
}


main "$@"; exit

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
