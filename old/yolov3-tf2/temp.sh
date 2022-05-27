#!/bin/bash

# SERVER_ADDR='localhost' python3.6 detect.py --image data/meme.jpg

# container_name=grpc_client_test
# mkdir -p data
# docker rm -f $container_name > /dev/null 2>&1
# docker create \
#     -it \
#     --volume=$(pwd)/data:/data \
#     --network=tf-grpc \
#     --name=$container_name \
#     --workdir='/root/yolov3-tf2' \
#     --env SERVER_ADDR=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' grpc_server) \
#     grpc_client_id_only \
#     python detect.py --image data/meme.jpg

# docker start $container_name 
# docker logs --follow grpc_client_test


docker rm -f misun
sudo kill -9 $(ps aux | grep unix_multi | awk '{print $2}') > /dev/null 2>&1


docker run -d --name misun ubuntu sleep 15
pid=$(docker container inspect --format='{{.State.Pid}}' misun)
echo $pid
pushd .
cd scripts
sudo python unix_multi_server.py &
server_pid=$!
sleep 2
# sudo python unix_client_send_pid.py $pid
sudo bash -c "echo 0 > /proc/sys/kernel/nmi_watchdog"
sudo python unix_client_send_pid.py $pid cpu-cycles,page-faults,minor-faults,major-faults,cache-misses,LLC-load-misses,LLC-store-misses,dTLB-load-misses,iTLB-load-misses misun
sudo bash -c "echo 1 > /proc/sys/kernel/nmi_watchdog"
popd
