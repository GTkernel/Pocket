#!/usr/bin/env bash

DEVICE=$1

if [[ "$DEVICE" = "cpu" ]]; then
    POCKET_FE_CPU=1.7 # 1.8
    POCKET_FE_MEM=$(bc <<< '1024 * 0.5')mb
    POCKET_BE_CPU=2.5 # 1
    POCKET_BE_MEM=$(bc <<< '1024 * 1.4')mb
    POCKET_BE_MEM_SWAP=$(bc <<< '1024 * 1.4 * 4')mb
    MONOLITHIC_CPU=2
    MONOLITHIC_MEM=$(bc <<< '1024 * 1.3')mb
    # POCKET_FE_CPU=1.2 # 1.8
    # POCKET_FE_MEM=$(bc <<< '1024 * 0.5')mb
    # POCKET_BE_CPU=4 # 1
    # POCKET_BE_MEM=$(bc <<< '1024 * 2')mb
    # POCKET_BE_MEM_SWAP=$(bc <<< '1024 * 2 * 4')mb
    # MONOLITHIC_CPU=2
    # MONOLITHIC_MEM=$(bc <<< '1024 * 1.3')mb
elif [[ "$DEVICE" = "gpu" ]]; then
    [[ SQUEEZE = "1" ]] && POCKET_FE_CPU=0.5 || POCKET_FE_CPU=1.8
    # [[ SQUEEZE = "1" ]] && POCKET_FE_CPU=0.5 || POCKET_FE_CPU=1.8
    POCKET_FE_MEM=$(bc <<< '1024 * 0.5')mb
    POCKET_BE_CPU=1
    POCKET_BE_MEM=$(bc <<< '1024 * 2.4')mb
    POCKET_BE_MEM_SWAP=$(bc <<< '1024 * 2.4 * 4')mb
    MONOLITHIC_CPU=2
    MONOLITHIC_MEM=$(bc <<< '1024 * 2.4')mb
fi