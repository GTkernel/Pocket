#!/bin/bash


mkdir -p data
me=$(whoami)
sudo chown -R $me data
sudo chgrp -R $me data

rm -rf data/*
# bash exp_script.sh help
# bash exp_script.sh pf-mon -n=2 --policy=1 --event=1
# bash exp_script.sh papi-mon -n=2 --policy=1 --event=3
# bash exp_script.sh papi -n=2 --policy=1 --event=3
# bash exp_script.sh pf -n=2 --policy=1

# Monolithic: pagefaults
for n in 1 3 5 10; do
    for iter in 1 2 3; do
        bash exp_script.sh pf-mon -n=$n
    done
done

# Monolithic: for each event 0, 3, 4
for e in 0 3 4; do
    for n in 1 3 5 10; do
        for iter in 1 2 3; do
            bash exp_script.sh papi-mon -n=$n --event=$e
        done
    done
done

# Pocket: pagefault
for p in 1 3; do
    for e in 0 3 4; do
        for n in 1 3 5 10; do
            for iter in 1 2 3; do
                bash exp_script.sh pf -n=$n --event=$e --policy=$p
            done
        done
    done
done

# Pocket: for each event 0, 3, 4
for p in 1 3; do
    for e in 0 3 4; do
        for n in 1 3 5 10; do
            for iter in 1 2 3; do
                bash exp_script.sh papi -n=$n --event=$e --policy=$p
            done
        done
    done
done

: '
    0: okay (instructions)
    1: o    (l1)
    2: o    (l2)
    3: o    (l3)
    4: o    (tlb)
'

# exit
# rm -rf data/*