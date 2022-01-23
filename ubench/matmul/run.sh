#!/bin/bash

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd $SCRIPT_DIR

# total_mem=2048
# # # bash _run.sh --policy=5 -n=6 --size=300 --total=$total_mem --file=num_static
# bash _run.sh --policy=3 -n=5 --size=3000 --total=2048 --file=num_static
# exit
total_mem=512
n=1
echo 4 > num_static
echo 12 > num_dynamic
# echo $n > num_static
# echo $n > num_dynamic
while true; do
    echo '=============================='
    echo '>>>>>' total_mem=${total_mem}mb

    echo '>>>>>' static
    n=$(cat num_static)
    bash _run.sh --policy=3 -n=$n --size=3000 --total=$total_mem --file=num_static
    echo
    echo '>>>>>' dynamic
    n=$(cat num_dynamic)
    bash _run.sh --policy=5 -n=$n --size=3000 --total=$total_mem --file=num_dynamic
    total_mem=$(bc <<< "$total_mem + 512")
done
# echo '>>>>>' static
# total_mem=1024
# n=5
# while true; do
#     echo '>>>>>' total_mem=${total_mem}mb
#     bash _run.sh --policy=3 -n=$n --size=2000 --total=$total_mem
#     total_mem=$(bc <<< "$total_mem" + 512)
#     n=$(cat numinstances)
# done
# bash _run.sh --policy=1 -n=2 --size=100
# bash _run.sh --policy 2