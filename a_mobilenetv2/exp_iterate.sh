#!/bin/bash


mkdir -p data
me=$(whoami)
sudo chown -R $me data
sudo chgrp -R $me data

bash exp_script.sh latency -n=10 --policy=1

# bash exp_script.sh latency -n=5 --policy=1

# rm -rf data/*
# bash exp_script.sh pf-mon -n=0 --policy=1 --event=1

# exit
# rm -rf data/*
# bash exp_script.sh papi -n=0 --policy=1 --event=3
# bash exp_script.sh papi-mon -n=0 --policy=1 --event=3
: '
    0: okay (instructions)
    1: o    (l1)
    2: o    (l2)
    3: o    (l3)
    4: o    (tlb)
'