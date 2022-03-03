#!/bin/bash

DEVICE=${1:-cpu}
ITER=${2:-3}

n=1

# echo '>>>>' varing all policy; echo
# for p in $(seq 0 8); do
#     for iter in $(seq 1 $ITER); do
#         bash exp_script.sh latency -n=$n --cpupolicy="func,ratio,0.$p" --mempolicy="func,ratio,0.$p" --device=$DEVICE 2>&1 | grep 'inference_time\|>>>>>>>' 
#     done
# done

echo '>>>>' varing cpu policy; echo
for p in $(seq 0 8); do
    for iter in $(seq 1 $ITER); do
        bash exp_script.sh latency -n=$n --cpupolicy="func,ratio,0.$p" --mempolicy="func,ratio,0.8" --device=$DEVICE 2>&1 | grep 'inference_time\|>>>>>>>' 
    done
done

echo '>>>>' varing memory policy; echo
for p in $(seq 0 8); do
    for iter in $(seq 1 $ITER); do
        bash exp_script.sh latency -n=$n --cpupolicy="func,ratio,0.8" --mempolicy="func,ratio,0.$p" --device=$DEVICE 2>&1 | grep 'inference_time\|>>>>>>>' 
    done
done
