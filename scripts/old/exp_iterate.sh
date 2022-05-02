#!/bin/bash

#!/bin/bash


mkdir -p data
me=$(whoami)
sudo chown -R $me data
sudo chgrp -R $me data
cd $(dirname $0)

cd ../tfrpc/proto
bash gen_proto.sh
cd -

rm -rf data/*
bash exp_script.sh temp-exp -n=3 --ratio=0.8 --resource-realloc=1
exit
truncate -s 0 ../temp
for ralloc in 1 0; do
    for n in $(seq 1 6); do
        echo '>>>>>>>>>>' n=$n, ralloc=$ralloc | tee -a ../temp
        for i in $(seq 1 2); do
            bash exp_script.sh temp-exp -n=$n --ratio=0.8 --resource-realloc=$ralloc >> ../temp 2>&1
        done
    done
done

# bash exp_script.sh temp-exp -n=0 --ratio=0.8 --resource-realloc=0
# bash exp_script.sh latency-mon -n=1 --ratio=0.5 --resource-realloc=1
# bash exp_script.sh latency -n=2 --ratio=0.5 --resource-realloc=1
exit
# for i in $(seq 1 10); do
#     bash exp_script.sh latency -n=15 --ratio=0.5 --resource-realloc=1
# done
# exit
for r in 0.3 0.4 0.5 0.6 0.7 0.8 0.9; do
    for i in $(seq 1 3); do
        bash exp_script.sh latency -n=10 --ratio=$r --resource-realloc=1
    done
done
exit

bash exp_script.sh latency -n=10 --ratio=0.5
bash exp_script.sh latency -n=10 --ratio=0.6
bash exp_script.sh latency -n=10 --ratio=0.7
bash exp_script.sh latency -n=10 --ratio=0.8
# bash exp_script.sh latency -n=10 --ratio=0.9
# bash exp_script.sh latency -n=10 --ratio=0.8
# bash exp_script.sh latency-mon -n=10 --ratio=0.8
# bash exp_script.sh rusage-mon -n=1 --ratio=0.5
# bash exp_script.sh perf-mon -n=1 --ratio=0.5
# bash exp_script.sh latency -n=1 --ratio=0.5
# bash exp_script.sh rusage -n=2 --ratio=0.5
# bash exp_script.sh perf -n=2 --ratio=0.5

exit

for ratio in 0.5 0.8; do
    echo ratio=$ratio
    for n in 1 5 10; do
        echo n=$n
        bash exp_script.sh measure-inference-throughput -n=$n --ratio=$ratio
        if [[ "$ratio" = "0.8" ]]; then
            continue
        fi
        bash exp_script.sh measure-inference-throughput-mon -n=$n
    done
done
exit

bash exp_script.sh measure-inference-throughput -n=1 --ratio=0.5
bash exp_script.sh measure-inference-throughput-mon -n=1 --ratio=0.5
exit
# bash exp_script.sh latency -n=5 --ratio=0.5 --fps=1
# exit
# # rm -rf data/*
# bash exp_script.sh scaling-mon -n=11 --ratio=0.5 --fps=1
# exit
# bash exp_script.sh scaling -n=1 --ratio=0.5 --fps=1
# exit

scaling_mon_has_run=0
commands=("scaling" "scaling-mon")
commands=("scaling")
for ratio in 0.8; do
    echo ratio=$ratio
    for command in ${commands[@]}; do
        if [[ "$command" = "scaling-mon" ]]; then
            if [[ $scaling_mon_has_run -eq 1 ]]; then
                continue
            else
                scaling_mon_has_run=1
            fi
        fi
        echo; echo command=$command
        for num in 1 5 10 15 20 25; do
            echo num=$num
            for i in $(seq 1 5); do
                bash exp_script.sh $command -n=$num --ratio=$ratio --fps=1
            done
        done
    done
done
exit

bash exp_script.sh scaling -n=1 --ratio=0.5 --fps=1
exit


# bash exp_script.sh thruput -n=2 --ratio=0.5 --fps=5
# exit
# bash exp_script.sh thruput-mon -n=2 --ratio=0.5 --fps=5
# exit

command=("thruput")
for command in "${command[@]}"; do
    echo command=$command
    for fps in 1 5 10 15 20; do
        echo fps=$fps
        bash exp_script.sh $command -n=10 --ratio=0.5 --fps=$fps
    done
done
for fps in 1 5 10 15 20; do
    bash exp_script.sh thruput -n=10 --ratio=0.8 --fps=$fps
done


exit
bash exp_script.sh thruput -n=2 --ratio=0.5 --fps=5
exit
# commands=("latency")
# for command in "${commands[@]}"; do
#     for i in 1 5 10; do
#         for j in 1 2 3; do
#             bash exp_script.sh $command -n=$i --ratio=0.5
#         done
#     done
# done
# exit

# commands=("perf-grpc" "perf-mon" "perf")
# commands=("perf-mon" "perf")
commands=("perf")

# for command in "${commands[@]}"; do
#     for i in 1 5 10; do
#         for j in 1 2 3 4 5 6 7 8 9 10; do
#             bash exp_script.sh $command -n=$i --resource-realloc=0
#         done
#     done
# done

for command in "${commands[@]}"; do
    for i in 1 5 10; do
        for j in 1 2 3 4 5 6 7 8 9 10; do
            bash exp_script.sh $command -n=$i --ratio=0.5
        done
    done
done



for command in "${commands[@]}"; do
    for i in 1 5 10; do
        for j in 1 2 3 4 5 6 7 8 9 10; do
            bash exp_script.sh $command -n=$i --ratio=0.8
        done
    done
done

exit

# bash exp_script.sh latency -n=10 --ratio=0.5 --resource-realloc=1
# bash exp_script.sh latency -n=10 --ratio=0.8 --resource-realloc=1
# bash exp_script.sh latency -n=10 --ratio=0.5 --resource-realloc=1 --physcpubind=10
# bash exp_script.sh latency -n=10 --ratio=0.8 --resource-realloc=1 --physcpubind=10
bash exp_script.sh latency-mon -n=10
# bash exp_script.sh latency-mon -n=10 --physcpubind=10
exit

bash exp_script.sh thruput -n=10 --ratio=0.5 --resource-realloc=1
bash exp_script.sh thruput -n=10 --ratio=0.8 --resource-realloc=1
bash exp_script.sh thruput -n=10 --ratio=0.5 --resource-realloc=1 --physcpubind=10
bash exp_script.sh thruput -n=10 --ratio=0.8 --resource-realloc=1 --physcpubind=10
bash exp_script.sh thruput-mon -n=10
bash exp_script.sh thruput-mon -n=10 --physcpubind=10
exit

## all commands
# commands=("latency-mon" "rusage-mon" "perf-mon" "latency" "rusage" "perf" "cprofile" "latency-grpc" "rusage-grpc" "perf-grpc" "cprofile-grpc")

## all pocket commands
# commands=("latency" "rusage" "perf" "cprofile")
# commands=("latency-mon" "rusage-mon" "perf-mon")
# commands=("latency-grpc" "rusage-grpc" "perf-grpc" "cprofile-grpc")

## all pocket-grpc commands
commands=("latency-mon")
# commands=("latency") # : okay

for command in "${commands[@]}"; do
    for i in 1 5 10 15 20 25 30; do
        for j in $(seq 1 10); do
            bash exp_script.sh $command -n=$i --resource-realloc=0
        done
    done
done

## feasibility check
# for command in "${commands[@]}"; do
#     bash exp_script.sh ${command} -n=10
# done

# ## feasibility check
# for command in "${commands[@]}"; do
#     bash exp_script.sh ${command} -n=2 --resource-realloc=1
# done

# ## feasibility check
# for command in "${commands[@]}"; do
#     bash exp_script.sh ${command} -n=10 --resource-realloc=1
# done


# for command in "${commands[@]}"; do
#     for i in 1 5 10; do
#         for j in 1 2 3 4 5 6 7 8 9 10; do
#             bash exp_script.sh $command -n=$i --resource-realloc=0
#         done
#     done
# done

# for command in "${commands[@]}"; do
#     for i in 1 5 10; do
#         for j in 1 2 3 4 5 6 7 8 9 10; do
#             bash exp_script.sh $command -n=$i --ratio=0.5
#         done
#     done
# done



# for command in "${commands[@]}"; do
#     for i in 1 5 10; do
#         for j in 1 2 3 4 5 6 7 8 9 10; do
#             bash exp_script.sh $command -n=$i --ratio=0.8
#         done
#     done
# done
