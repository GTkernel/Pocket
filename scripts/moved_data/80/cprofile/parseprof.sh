#!/bin/bash

find . -name "*.log" -exec rm -f {} \;

for folder1 in *; do
    if [[ -f $folder1 ]]; then
        continue
    fi
    if [ "${folder1}" == "aggregate" ]; then
        continue
    fi
    workdir=$(pwd)
    cd $folder1
        for folder2 in *; do
            cd $folder2
                for file in *; do
                    if [ "${file: -4}" == ".log" ]; then
                        continue
                    fi
                    python3 $workdir/parseprof -f $file
                done
            cd -
        done
    cd $workdir
done