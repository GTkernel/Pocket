#!/bin/bash


mkdir -p data
me=$(whoami)
sudo chown -R $me data
sudo chgrp -R $me data


bash exp_script.sh latency -n=1 --policy=1 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2
# bash exp_script.sh latency -n=8 --policy=3 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2
# bash exp_script.sh latency -n=8 --policy=3 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2
# bash exp_script.sh latency -n=9 --policy=3 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2
# bash exp_script.sh latency -n=10 --policy=3 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2


# bash exp_script.sh latency -n=1 --policy=2 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2
# bash exp_script.sh latency -n=1 --policy=2 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2
# bash exp_script.sh latency -n=1 --policy=2 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2
# bash exp_script.sh latency -n=3 --policy=2 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2
# bash exp_script.sh latency -n=3 --policy=2 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2
# bash exp_script.sh latency -n=7 --policy=2 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2
# bash exp_script.sh latency -n=7 --policy=2 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2
# bash exp_script.sh latency -n=8 --policy=2 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2
# bash exp_script.sh latency -n=9 --policy=2 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2
exit

echo '>>>>'  pocket
echo
for n in $(seq 5 10); do
    echo n=$n
    for i in $(seq 1 3); do
        bash exp_script.sh latency -n=$n --policy=1 2>&1 |  grep 'inference_time\|>>>>>>>'
        echo
        # bash exp_script.sh latency-mon -n=10 --ratio=0.5 --resource-realloc=1
    done
done
for p in $(seq 2 3); do
    for n in $(seq 1 10); do
        echo n=$n
        for i in $(seq 1 3); do
            bash exp_script.sh latency -n=$n --policy=$p 2>&1 |  grep 'inference_time\|>>>>>>>'
            echo
            # bash exp_script.sh latency-mon -n=10 --ratio=0.5 --resource-realloc=1
        done
    done
done
echo
echo '>>>>'  monolithic
echo
for n in $(seq 1 10); do
    echo n=$n
    for i in $(seq 1 3); do
        bash exp_script.sh latency-mon -n=$n --policy=$p 2>&1 |  grep 'inference_time\|>>>>>>>'
        echo
        # bash exp_script.sh latency-mon -n=10 --ratio=0.5 --resource-realloc=1
    done
done
exit
