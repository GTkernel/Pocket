# **Pocket**
This repository contains source code and script files for the Pocket paper, which will be presented at [Eurosys'23](https://2023.eurosys.com). Technical details and design decisions are available in the published paper.

A tag for submitted artifact: [artifact-evaluation](https://github.com/GTkernel/Pocket/releases/tag/artifact-evaluation)

(Bibtex for citation will be added once it gets available.)

## Getting Started Instructions 
<!--
30 minutes
https://docs.google.com/document/d/1pqzPtLVIvwLwJsZwCb2r7yzWMaifudHe1Xvn42T4CcA/edit
-->
### Prerequisite
* Ubuntu 18.04
* a single x86_64 machine
* required RAM size, core num
* Software dependencies specified in the following sections including Docker

### Install Dependencies
* This phase installs software dependencies. Root previleges required. (10 miniutes)
```
cd scripts
# To install dependencies to run cpu-based applications
./install prerequisite --gpu=0 # --gpu=0 can be omitted. # if you're a root user
sudo --preserve-env=USER ./install prerequisite --gpu=0 # if you're using sudo privilege as a regular user.
# To install dependencies to run gpu-based applications, additionally cuda related dependencies have to be installed
./install prerequisite --gpu=1
```
* **Rebooting** the machine is required. After installation completes, the prompt will ask if you'd like to reboot immediately. You can choose `No` to postpone rebooting, but you need to reboot your machine to use **Pocket** properly.


### Launch Hello-World Pocket 
* **Build a minimal Pocket application**:
This command will build minimal benchmark.
```
cd scripts
./install hello-world --gpu=0 # or --gpu=1 or omit # no root privilege required.
```
* **Launch a minimal Pocket application**: 
```
./launch hello-world
```

## About Pocket
### Source Tree
```
pocket
├── applications                    # Benchmark
│   ├── mobilenetv2
│   ├── resnet50
│   ├── smallbert
│   ├── ssdmobilenetv2_320x320
│   ├── ssdresnet50v1_640x640
│   └── talkingheads
├── firecracker-prep                # Scripts for generating FireCracker compatible filesystem images
├── pocket                          # Pocket binary
├── resources                       # input data and other artifacts
├── scripts                         # scripts for building and running Pocket
└── tfrpc                           # interface definition between Pocket FE and BE
```

## Detailed Instructions
### Build All Model Set
* This process build all application images that are evaluated in Pocket paper. This phase takes from several hours to 1 day. In this phase all dependencies inside the application image. No other configuration is needed apart from running the script.
```
# Build all application binaries for CPU
./install all-pockets # `--gpu=0` can be added

# for GPU
./install all-pockets --gpu=1
```
### @Todo: Run Pocket---Launch All Experiment 
* Experiments can be replicated with the command `./launch`.
* Each of these subcommands executes a full set of experiments and takes several hours to complete, so you may want to use this command with some flags such that you can more focus on your interest of evaluation/assesement.
```
./launch latency # The most basic command to verify functionality. The others are for specific experiments.
./launch latency-gpu
./launch eval-policy
./launch exec-breakdown
```
<!-- ./launch hw-counters
./launch latency #sleep -->

### System Requirement
* Pocket is built and tested on the environment as below:

| Items            	| Specification                                                                     	|
|------------------	|-----------------------------------------------------------------------------------	|
| Processors       	| Intel(R) Xeon(R) CPU E5-2670 v3 @ 2.30GHz;<br>2 Processors; 24 cores; 48 threads  	|
| GPU              	| NVIDIA K80 (only for GPU experiments)                                             	|
| Memory           	| 128MiB                                                                            	|
| Operating System 	| Ubuntu 18.04.3 LTS<br>GNU/Linux 4.15.0-76-generic x86_64                          	|
| Runtime/Library  	| TensorFlow:2.1.0; GCC 7.4.0 python 3.6.9<br>Docker version 20.10.8, build 3967b7d 	|

* It is expected that Pocket can be successfully run on any multi-core commodity server-grade machine with Ubuntu18.04 or newer version.

### Internal Operation
* To summarize how you can launch *pocketized* app

> (1) Pocketizing: have your application separated into two pieces
>
> (2) Run Pocket service backend
>
> (3) Run Pocket application frontend

* This section explains (2) and (3), (1) will be covered in one of the following sections, [Make Your Own Pocket](#).
---
* Internally, `Pocket` is built on top of Docker. After you have an application separated into 2 pieces, **you need to launch shared backend first**. This can be wrapped by `pocket` CLI, but what it does is basically launching the container like below.

```
docker run \
    -d \
    --privileged \
    --name=$server_container_name \
    --workdir='/root' \
    --env YOLO_SERVER=1 \
    --ip=$server_ip \
    --ipc=shareable \
    --cpus=1.0 \
    --memory=1024mb \
    --volume=/sys/fs/cgroup/:/cg \
    $server_image \
    python server.py
```
* Then you need to also run `pocket`ized application—frontend, with the something like the command below. This process is wrapped by `pocket` CLI.
```
pocket \
    run \
        --measure-latency $dir \
        -d \
        -b pocket-smallbert-application \
        -t ${container_name} \
        -s ${server_container_name} \
        --memory=$(bc <<< '1024 * 0.25')mb \
        --cpus=1.3 \
        --env POCKET_MEM_POLICY=${POCKET_MEM_POLICY} \
        --env POCKET_CPU_POLICY=${POCKET_CPU_POLICY} \
        --workdir='/root/smallbert' \
        -- python3 app.pocket.py &
```
* Resource budget, MEM, CPU management policy should be specified. Detailed information on resource management policies in `Pocket` can be found in the paper.

### Troubleshooting
* Currently Pocket has been tested on Ubuntu 18.04 and amd64 only.
* All install and build process should be launched one of the (non-root) user `$HOME`
* You need to have a sudo command access privilige.

### Make Your Own Pocket
* Make a Stub File
* Generate a Wrapper for Front End (Pocket-application or Pocket)
* Generate a Handler in Back End (Pocket-service)
* Define the Interface for Them
* Run Your Application

## Potential Usage of Pocket
The design idea of Pocket can be introduced anywhere there are heavy complex runtimes, scarce computing resource, and multiple instances sharing the technically same resources.
