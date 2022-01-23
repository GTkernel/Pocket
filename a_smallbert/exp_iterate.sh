#!/bin/bash


mkdir -p data
me=$(whoami)
sudo chown -R $me data
sudo chgrp -R $me data

# bash exp_script.sh latency -n=1 --policy=1 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2
# bash exp_script.sh latency -n=1 --policy=1 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2
# bash exp_script.sh latency -n=2 --policy=1 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2
# bash exp_script.sh latency -n=2 --policy=1 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2
# bash exp_script.sh latency -n=8 --policy=3 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2
# bash exp_script.sh latency -n=9 --policy=3 2>&1 |  grep 'inference_time\|>>>>>>>' | cut -d"=" -f2
# exit
echo '>>>>'  pocket
echo
for p in $(seq 1 3); do
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
bash exp_script.sh latency -n=0 --ratio=0.5 --resource-realloc=1
exit
bash exp_script.sh latency-mon -n=0 --ratio=0.5 --resource-realloc=1
exit


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
bash exp_script.sh latency -n=10 --ratio=0.9
exit
bash exp_script.sh latency-mon -n=1 --ratio=0.5
bash exp_script.sh rusage-mon -n=1 --ratio=0.5
bash exp_script.sh perf-mon -n=1 --ratio=0.5

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
# bash exp_script.sh measure-inference-throughput -n=1 --ratio=0.5
# exit
bash exp_script.sh measure-inference-throughput-mon -n=1 --ratio=0.5
exit

# for i in $(seq 1 10); do
#     bash exp_script.sh latency -n=0 --resource-realloc=0
#     docker logs -f pocket-client-0000
# done
# exit
# bash exp_script.sh scaling-mon -n=1 --ratio=0.5 --fps=1
# exit



scaling_mon_has_run=0
commands=("scaling" "scaling-mon")
commands=("scaling-mon")
for ratio in 0.5 0.8; do
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

# commands=("latency-mon" "rusage-mon" "perf-mon" "latency" "rusage" "perf" "cprofile")
commands=("latency" "latency-mon")


# for command in "${commands[@]}"; do
#     for i in 1 5 10; do
#         for j in 1 2 3 4 5 6 7 8 9 10; do
#             bash exp_script.sh $command -n=$i --ratio=0.5
#         done
#     done
# done

for command in "${commands[@]}"; do
    for i in 1 5 10; do
        for j in 1 2 3 4 5 6 7 8 9 10; do
            bash exp_script.sh $command -n=$i --ratio=0.8
        done
    done
done




# killall -9 pocketd
# sleep 3
# sudo ./pocket/pocketd &
# sleep 3
# bash ./exp_script.sh rusage -n=1

# killall -9 pocketd
# sleep 3
# sudo ./pocket/pocketd &
# sleep 3
# bash ./exp_script.sh rusage -n=5

# killall -9 pocketd
# sleep 3
# sudo ./pocket/pocketd &
# sleep 3
# bash ./exp_script.sh rusage -n=10


# killall -9 pocketd
# sleep 3
# sudo ./pocket/pocketd &
# sleep 3
# bash ./exp_script.sh cprofile -n=1

# killall -9 pocketd
# sleep 3
# sudo ./pocket/pocketd &
# sleep 3
# bash ./exp_script.sh cprofile -n=5

# killall -9 pocketd
# sleep 3
# sudo ./pocket/pocketd &
# sleep 3
# bash ./exp_script.sh cprofile -n=10


# killall -9 pocketd
# sleep 3
# sudo ./pocket/pocketd &
# sleep 3
# bash ./exp_script.sh perf -n=1

# killall -9 pocketd
# sleep 3
# sudo ./pocket/pocketd &
# sleep 3
# bash ./exp_script.sh perf -n=5

# killall -9 pocketd
# sleep 3
# sudo ./pocket/pocketd &
# sleep 3
# bash ./exp_script.sh perf -n=10

# exit



# for i in $(seq 1 4); do
#     killall -9 pocketd
#     sleep 3
#     sudo ./pocket/pocketd --ratio=0.5 &
#     sleep 3
#     bash ./exp_script.sh rusage -n=1
# done

# for i in $(seq 1 4); do
#     killall -9 pocketd
#     sleep 3
#     sudo ./pocket/pocketd --ratio=0.5 &
#     sleep 3
#     bash ./exp_script.sh rusage -n=5
# done

# for i in $(seq 1 4); do
#     killall -9 pocketd
#     sleep 3
#     sudo ./pocket/pocketd --ratio=0.5 &
#     sleep 3
#     bash ./exp_script.sh rusage -n=10
# done


# for i in $(seq 1 4); do
#     killall -9 pocketd
#     sleep 3
#     sudo ./pocket/pocketd --ratio=0.5 &
#     sleep 3
#     bash ./exp_script.sh cprofile -n=1
# done

# for i in $(seq 1 4); do
#     killall -9 pocketd
#     sleep 3
#     sudo ./pocket/pocketd --ratio=0.5 &
#     sleep 3
#     bash ./exp_script.sh cprofile -n=5
# done

# for i in $(seq 1 2); do
#     sudo ./pocket/pocketd --ratio=0.5 &
#     sleep 3
#     killall -9 pocketd
#     sleep 3
#     bash ./exp_script.sh cprofile -n=10
# done


# for i in $(seq 1 4); do
#     killall -9 pocketd
#     sleep 3
#     sudo ./pocket/pocketd --ratio=0.5 &
#     sleep 3
#     bash ./exp_script.sh perf -n=1
# done

# for i in $(seq 1 4); do
#     killall -9 pocketd
#     sleep 3
#     sudo ./pocket/pocketd --ratio=0.5 &
#     sleep 3
#     bash ./exp_script.sh perf -n=5
# done

# for i in $(seq 1 4); do
#     killall -9 pocketd
#     sleep 3
#     sudo ./pocket/pocketd --ratio=0.5 &
#     sleep 3
#     bash ./exp_script.sh perf -n=10
# done



# exit

echo 0.8

# for i in $(seq 1 9); do
#     killall -9 pocketd
#     sleep 3
#     sudo ./pocket/pocketd --ratio=0.8 &
#     sleep 3
#     bash ./exp_script.sh rusage -n=1
# done

# for i in $(seq 1 9); do
#     killall -9 pocketd
#     sleep 3
#     sudo ./pocket/pocketd --ratio=0.8 &
#     sleep 3
#     bash ./exp_script.sh rusage -n=5
# done

# for i in $(seq 1 9); do
#     killall -9 pocketd
#     sleep 3
#     sudo ./pocket/pocketd --ratio=0.8 &
#     sleep 3
#     bash ./exp_script.sh rusage -n=10
# done


# for i in $(seq 1 9); do
#     killall -9 pocketd
#     sleep 3
#     sudo ./pocket/pocketd --ratio=0.8 &
#     sleep 3
#     bash ./exp_script.sh perf -n=1
# done

# for i in $(seq 1 2); do
#     killall -9 pocketd
#     sleep 3
#     sudo ./pocket/pocketd --ratio=0.8 &
#     sleep 3
#     bash ./exp_script.sh perf -n=5
# done

# for i in $(seq 1 9); do
#     killall -9 pocketd
#     sleep 3
#     sudo ./pocket/pocketd --ratio=0.8 &
#     sleep 3
#     bash ./exp_script.sh perf -n=10
# done


# for i in $(seq 1 9); do
#     killall -9 pocketd
#     sleep 3
#     sudo ./pocket/pocketd --ratio=0.8 &
#     sleep 3
#     bash ./exp_script.sh cprofile -n=1
# done

# for i in $(seq 1 4); do
#     killall -9 pocketd
#     sleep 3
#     sudo ./pocket/pocketd --ratio=0.8 &
#     sleep 3
#     bash ./exp_script.sh cprofile -n=5
# done

# for i in $(seq 1 9); do
#     sudo ./pocket/pocketd --ratio=0.8 &
#     sleep 3
#     killall -9 pocketd
#     sleep 3
#     bash ./exp_script.sh cprofile -n=10
# done

# exit

# for i in $(seq 1 10); do
#     bash ./exp_script.sh motivation -n=1
# done