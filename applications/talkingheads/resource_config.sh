#!/usr/bin/env bash

DEVICE=$1

if [[ "$DEVICE" = "cpu" ]]; then
    POCKET_FE_CPU=1.7
    POCKET_FE_MEM=$(bc <<< '1024 * 0.25')mb
    POCKET_BE_CPU=2
    POCKET_BE_MEM=$(bc <<< '1024 * 2.2')mb
    POCKET_BE_MEM_SWAP=$(bc <<< '1024 * 2.2 * 4')mb
    MONOLITHIC_CPU=2
    MONOLITHIC_MEM=$(bc <<< '1024 * 2.2')mb
    # POCKET_FE_CPU=1.8
    # POCKET_FE_MEM=$(bc <<< '1024 * 0.25')mb
    # POCKET_BE_CPU=1
    # POCKET_BE_MEM=$(bc <<< '1024 * 2.2')mb
    # POCKET_BE_MEM_SWAP=$(bc <<< '1024 * 2.2 * 4')mb
    # MONOLITHIC_CPU=2
    # MONOLITHIC_MEM=$(bc <<< '1024 * 2.2')mb
elif [[ "$DEVICE" = "gpu" ]]; then
    POCKET_FE_CPU=1.8
    POCKET_FE_MEM=$(bc <<< '1024 * 0.25')mb
    POCKET_BE_CPU=1
    POCKET_BE_MEM=$(bc <<< '1024 * 2.2')mb
    POCKET_BE_MEM_SWAP=$(bc <<< '1024 * 2.2 * 4')mb
    MONOLITHIC_CPU=2
    MONOLITHIC_MEM=$(bc <<< '1024 * 2.2')mb
fi