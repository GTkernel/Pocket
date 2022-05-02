#!/usr/bin/env bash

DEVICE=$1

if [[ "$DEVICE" = "cpu" ]]; then
    POCKET_FE_CPU=1.3
    POCKET_FE_MEM=512mb
    POCKET_BE_CPU=1
    POCKET_BE_MEM=$(bc <<< '1024 * 0.9')mb
    POCKET_BE_MEM_SWAP=$(bc <<< '1024 * 0.9 * 4')mb
    # POCKET_BE_MEM=$(bc <<< '1024 * 2')mb
    MONOLITHIC_CPU=1.5
    MONOLITHIC_MEM=$(bc <<< '1024 * 0.9')mb
elif [[ "$DEVICE" = "gpu" ]]; then
    POCKET_FE_CPU=1.3
    POCKET_FE_MEM=512mb
    POCKET_BE_CPU=1
    POCKET_BE_MEM=$(bc <<< '1024 * 2.2')mb
    POCKET_BE_MEM_SWAP=$(bc <<< '1024 * 2.2 * 4')mb
    MONOLITHIC_CPU=1.5
    MONOLITHIC_MEM=$(bc <<< '1024 * 2.2')mb
fi