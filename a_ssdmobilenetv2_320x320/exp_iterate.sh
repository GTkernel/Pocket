#!/bin/bash

mkdir -p data
me=$(whoami)
sudo chown -R $me data
sudo chgrp -R $me data
DEVICE=${1:-cpu}
ITER=${2:-3}

# bash exp_script.sh latency -n=1 --policy=1 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2
# exit
echo '>>>>'  pocket
echo
for p in 1 3 4; do
    for n in $(seq 1 10); do
        echo n=$n
        for i in $(seq 1 $ITER); do
            bash exp_script.sh latency -n=$n --policy=$p --device=$DEVICE 2>&1 |  grep 'inference_time\|>>>>>>>'
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
    for i in $(seq 1 $ITER); do
        bash exp_script.sh latency-mon -n=$n --policy=$p --device=$DEVICE 2>&1 |  grep 'inference_time\|>>>>>>>'
        echo
        # bash exp_script.sh latency-mon -n=10 --ratio=0.5 --resource-realloc=1
    done
done
exit