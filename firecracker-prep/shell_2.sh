#!/usr/bin/env bash

function main() {
    COMMAND=$1
    case $COMMAND in
        on)
            config
            turn_on
            ;;
        off)
            turn_off
            ;;
        *)
    esac
}

function config() {
    arch=`uname -m`
    kernel_path=$(pwd)"/hello-vmlinux.bin"

    if [[ ${arch} = "x86_64" ]]; then
        curl --unix-socket /tmp/firecracker.socket -i \
        -X PUT 'http://localhost/boot-source'   \
        -H 'Accept: application/json'           \
        -H 'Content-Type: application/json'     \
        -d "{
                \"kernel_image_path\": \"${kernel_path}\",
                \"boot_args\": \"console=ttyS0 reboot=k panic=1 pci=off\"
        }"
    elif [[ ${arch} = "aarch64" ]]; then
        curl --unix-socket /tmp/firecracker.socket -i \
        -X PUT 'http://localhost/boot-source'   \
        -H 'Accept: application/json'           \
        -H 'Content-Type: application/json'     \
        -d "{
                \"kernel_image_path\": \"${kernel_path}\",
                \"boot_args\": \"keep_bootcon console=ttyS0 reboot=k panic=1 pci=off\"
        }"
    else
        echo "Cannot run firecracker on $arch architecture!"
        exit 1
    fi

    rootfs_path=$(pwd)"/hello-rootfs.ext4"
    curl --unix-socket /tmp/firecracker.socket -i \
        -X PUT 'http://localhost/drives/rootfs' \
        -H 'Accept: application/json'           \
        -H 'Content-Type: application/json'     \
        -d "{
                \"drive_id\": \"rootfs\",
                \"path_on_host\": \"${rootfs_path}\",
                \"is_root_device\": true,
                \"is_read_only\": false
        }"
}

function turn_on() {
    curl --unix-socket /tmp/firecracker.socket -i \
        -X PUT 'http://localhost/actions'       \
        -H  'Accept: application/json'          \
        -H  'Content-Type: application/json'    \
        -d '{
            "action_type": "InstanceStart"
        }'
}

https://github.com/firecracker-microvm/firecracker/blob/main/docs/api_requests/actions.md
function turn_off() {
    curl --unix-socket /tmp/firecracker.socket -i \
        -X PUT "http://localhost/actions" \
        -d '{ "action_type": "SendCtrlAltDel" }'
}

main "$@"; exit