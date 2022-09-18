#!/usr/bin/env bash

function main() {
    rm -f /tmp/firecracker.socket
    ./firecracker --api-sock /tmp/firecracker.socket
}

main "$@"; exit