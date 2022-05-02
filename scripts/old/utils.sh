#!/bin/bash

GET_CONTAINER_PID='{{.State.Pid}}'
GET_CONTAINER_ID='{{.Id}}'
GET_CONTAINER_CREATED='{{.Created}}'
GET_CONTAINER_STARTED='{{.State.StartedAt}}'
GET_CONTAINER_FINISHED='{{.State.FinishedAt}}'
GET_CONTAINER_IPADDRESS='{{.NetworkSettings.IPAddress}}'
NUMCPU=$(nproc)

function utils_get_container_id() {
    local name=$1
    id=$(docker inspect -f '{{.Id}}' $name)
    echo $id
}

function utils_get_container_pid() {
    local name=$1
    pid=$(docker inspect -f '{{.State.Pid}}' $name)
    echo $pid
}

function utils_attach_root() {
    local target_id=$(utils_get_container_id $1)
    local target_pid=$(utils_get_container_pid $1)

    docker exec $target_id [ -b /dev/sda1 ] || mknod --mode 0600 /dev/sda1 b 8 1
    docker exec $target_id mkdir -p /hostroot
    sudo nsenter --target $target_pid --mount --uts --ipc --net -- mount /dev/sda1 /hostroot
}