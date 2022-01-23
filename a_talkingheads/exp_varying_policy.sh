#!/bin/bash

n=1
for p in $(seq 0 8); do
    for iter in 1 2 3; do
        bash exp_script.sh latency -n=$n --cpupolicy="func,ratio,0.$p" --mempolicy="func,ratio,0.$p" 2>&1 | grep 'inference_time\|>>>>>>>'    
        done
done