#!/usr/bin/env bash
# set -x
FCROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

function main( ){
    chmod 0600 docker-to-fc/ssh-keys/id_rsa
    COMMAND=$1
    case $COMMAND in
        install)
            install
            ;;
        basic-test)
            test_firectl_all
            ;;
        network-test)
            network_test
            ;;
        experiment)
            experiment
            ;;
        boottime)
            boottime
            ;;
        turnoff-multi)
            turnoff_multi "${@:2}"
            ;;
        ssh-command)
            ssh_command "${@:2}"
            ;;
        dry-run)
            dry_run
            ;;
        *)
            print_error "No such command: $COMMAND"
            ;;
    esac
}

function install() {
    print_info "Setting FireCracker.."
    print_info "Setting up KVM access.."
    print_info "sudo access is required."

    sudo setfacl -m u:${USER}:rw /dev/kvm
    [ -r /dev/kvm ] && [ -w /dev/kvm ] && echo "KVM Access OK" || echo "KVM Access FAIL"
    
    print_info "Getting the FireCracker Binary.."
    # https://arun-gupta.github.io/firecracker-getting-started/
    release_url="https://github.com/firecracker-microvm/firecracker/releases"
    # latest=$(basename $(curl -fsSLI -o /dev/null -w  %{url_effective} ${release_url}/latest))
    version=v1.1.0
    arch=`uname -m`
    curl -L ${release_url}/download/${version}/firecracker-${version}-${arch}.tgz | tar -xz
    mv release-${version}-$(uname -m)/firecracker-${version}-$(uname -m) "${FCROOT}"/firecracker

    getting_default_kernel_fs
    install_firectl
    test_firectl_all
    # # test_firectl_minimal
    custom_rootfs_and_kernel
}

function network_test() {
    NUMINSTANCE=1
    network_init $NUMINSTANCES
    network_run
    network_fin
}

function ssh_command() {
    local command="$@"
    VM_IP="$(./util_ipam.sh -v ${ID:-0})"
    local SSH="ssh -i docker-to-fc/ssh-keys/id_rsa -v -F docker-to-fc/ssh-keys/ssh-config root@${VM_IP}"
    ${SSH} $command
}

function install_firectl() {
    # https://github.com/firecracker-microvm/firectl
    # https://s8sg.medium.com/quick-start-with-firecracker-and-firectl-in-ubuntu-f58aeedae04b
    # https://gruchalski.com/posts/2021-02-14-firecracker-vmm-with-additional-disks/
    if ! which go; then
        print_warning "Go is not found in your system. Go is getting installed..."
        rm -rf /usr/local/go && tar -C /usr/local -xzf go1.20.1.linux-amd64.tar.gz
        sudo apt update -y
        sudo apt upgrade -y
        sudo apt install golang-go -y
    fi

    [[ -d firectl ]] && rm -rf firectl

    git clone https://github.com/firecracker-microvm/firectl.git
    cd firectl
    make clean
    make build-in-docker
    cd -
    # INSTALLPATH=${FCROOT}/firectl make install
}

function test_firectl_minimal() {
    ./firectl/firectl \
        --firecracker-binary=${FCROOT}/firecracker \
        --kernel=hello-vmlinux.bin \
        --root-drive=hello-rootfs.ext4:ro \
        --kernel-opts="init=/bin/systemd noapic reboot=k panic=1 pci=off nomodules console=ttyS0"
    # login: root/root
    # stop: reboot or sigterm
    # sudo kill -TERM $(pgrep -l firectl | awk '{ print $1 }')
}

function test_firectl_all() {
    ./firectl/firectl \
        --firecracker-binary=${FCROOT}/firecracker \
        --kernel=hello-vmlinux.bin \
        --root-drive=hello-rootfs.ext4:ro \
        --kernel-opts="init=/bin/systemd noapic reboot=k panic=1 pci=off nomodules console=ttyS0"
    # login: root/root
    # stop: reboot or sigterm
    # sudo kill -TERM $(pgrep -l firectl | awk '{ print $1 }')
}

function getting_default_kernel_fs() {
    print_info "Getting the kernel and rootfs.."
    arch=`uname -m`
    dest_kernel="hello-vmlinux.bin"
    dest_rootfs="hello-rootfs.ext4"
    image_bucket_url="https://s3.amazonaws.com/spec.ccfc.min/img/quickstart_guide/$arch"

    rm -rf $dest_kernel $dest_rootfs

    if [ ${arch} = "x86_64" ]; then
        kernel="${image_bucket_url}/kernels/vmlinux.bin"
        rootfs="${image_bucket_url}/rootfs/bionic.rootfs.ext4"
    elif [ ${arch} = "aarch64" ]; then
        kernel="${image_bucket_url}/kernels/vmlinux.bin"
        rootfs="${image_bucket_url}/rootfs/bionic.rootfs.ext4"
    else
        echo "Cannot run firecracker on $arch architecture!"
        exit 1
    fi

    echo "Downloading $kernel..."
    curl -fsSL -o $dest_kernel $kernel

    echo "Downloading $rootfs..."
    curl -fsSL -o $dest_rootfs $rootfs

    echo "Saved kernel file to $dest_kernel and root block device to $dest_rootfs."

}

function custom_rootfs_and_kernel() {
    # git clone https://github.com/anyfiddle/firecracker-rootfs-builder.git
    cd docker-to-fc
    mkdir -p output
    push_images
    docker build -t kernel-rootfs-builder --no-cache .

    apps=(ssdresnet50v1)
    # apps=(mobilenetv2 resnet50 smallbert ssdmobilenetv2 ssdresnet50v1 smallbert talkingheads)
    for app in ${apps[@]}; do
        local dir=${app}
        if [[ "$app" = "ssdmobilenetv2" ]]; then
            dir=ssdmobilenetv2_320x320
        elif [[ $app = "ssdresnet50v1" ]]; then
            dir=ssdresnet50v1_640x640
        fi
        rm -f ubuntu-${app}.ext4 ubuntu-vmlinux
        docker run \
            --rm \
            --privileged \
            --volume=/var/run/docker.sock:/var/run/docker.sock \
            --volume=$(pwd)/output:/output \
            --volume=$(pwd)/scripts:/scripts \
            --volume=$(pwd)/workspace:/workspace \
            --volume=$(pwd)/ssh-keys:/ssh-keys \
            --volume=$(pwd)/../../resources/models:/tmp-models \
            --volume=$(pwd)/../../resources/coco/val2017:/tmp-coco2017 \
            --volume=$(pwd)/../../applications/${dir}:/tmp-${app} \
            kernel-rootfs-builder \
            bash /scripts/create-rootfs.sh misunpark/pocket-${app}-cpu-monolithic:latest $(pwd) ${app} ${dir}
        docker volume prune -f
        # read -rsp $'Press any key to continue...\n' -n1 key
        print_debug "Exporting ${app}"
        cp output/vmlinux ubuntu-vmlinux
        cp output/image.ext4 ubuntu-${app}.ext4
        # truncate -s 5G ubuntu.ext4
        e2fsck -f ubuntu-${app}.ext4
        resize2fs -M ubuntu-${app}.ext4
            # mkdir -p misun
            # sudo mount ubuntu-${app}.ext4 misun
            # ls -al misun/usr/local/lib
            # ls -al misun/usr/local/lib/python3.6/dist-packages
            # sudo umount misun
            # rmdir misun


        ## To run testing app, uncomment below lines
        # print_info "Running ${app}"

        # local empty_fs=empty.ext4
        # if [[ ! -f $empty_fs ]]; then
        #     dd if=/dev/zero of="${empty_fs}" bs=1M count=1024
        #     mkfs.ext4 "${empty_fs}"
        # fi

        # local add_drive=fc-empty.ext4
        # local add_drive2=fc-empty-2.ext4
        # rm -f $add_drive.ext4 $add_drive2.ext4
        # cp ${empty_fs} ${add_drive}
        # cp ${empty_fs} ${add_drive2}

        # read -rsp $'Press any key to continue...\n' -n1 key
        # ${FCROOT}/firectl/firectl \
        #     --firecracker-binary=${FCROOT}/firecracker \
        #     --kernel=ubuntu-vmlinux \
        #     --root-drive=ubuntu-${app}.ext4:ro \
        #     --add-drive="${add_drive}":rw \
        #     --add-drive="${add_drive2}":rw \
        #     --kernel-opts="init=/bin/systemd noapic reboot=k panic=1 pci=off nomodules console=ttyS0"
    done
    cd -
}

function dry_run() {
    # git clone https://github.com/anyfiddle/firecracker-rootfs-builder.git
    # cd docker-to-fc

    sudo setfacl -m u:${USER}:rw /dev/kvm
    [ -r /dev/kvm ] && [ -w /dev/kvm ] && echo "KVM Access OK" || echo "KVM Access FAIL"

    local empty_fs=empty.ext4
    if [[ ! -f $empty_fs ]]; then
        dd if=/dev/zero of="${empty_fs}" bs=1M count=1024
        mkfs.ext4 "${empty_fs}"
    fi

    apps=(resnet50)
    # apps=(mobilenetv2 resnet50 smallbert ssdmobilenetv2 ssdresnet50v1 smallbert talkingheads)
    for app in ${apps[@]}; do
        print_info "Running ${app}"

        local add_drive=fc-empty.ext4
        local add_drive2=fc-empty-2.ext4
        rm -f $add_drive.ext4 $add_drive2.ext4
        cp ${empty_fs} ${add_drive}
        cp ${empty_fs} ${add_drive2}

        ${FCROOT}/firectl/firectl \
            --firecracker-binary=${FCROOT}/firecracker \
            --kernel=docker-to-fc/ubuntu-vmlinux \
            --root-drive=docker-to-fc/ubuntu-${app}.ext4:ro \
            --add-drive="${add_drive}":rw \
            --add-drive="${add_drive2}":rw \
            --kernel-opts="init=/bin/systemd noapic reboot=k panic=1 pci=off nomodules console=ttyS0"
    done
    # cd - > /dev/null 2>&1
}

function multi_run() {
    # start=$(date +%s.%N)
    local cpubudget=$1
    local app=$2
    local num=$3

    sudo setfacl -m u:${USER}:rw /dev/kvm
    [ -r /dev/kvm ] && [ -w /dev/kvm ] && echo "KVM Access OK" || echo "KVM Access FAIL"

    fin_multiple_network $num
    init_multiple_network $num
    sleep 5
    # end=$(date +%s.%N)
    # echo here!!!!
    # bc <<< "$end - $start";exit


    run_multiple_fc $cpubudget $app $num
    # fin_multiple_network $num
}

function run_multiple_fc() {
    local cpubudget=$1
    local app=$2
    local num=$3
    # sudo setfacl -m u:${USER}:rw /dev/kvm
    # [ -r /dev/kvm ] && [ -w /dev/kvm ] && echo "KVM Access OK" || echo "KVM Access FAIL"

    # echo MAC1=$MAC1
    # echo MAC2=$MAC2
    # exit

    # SSH="ssh -i docker-to-fc/ssh-keys/id_rsa.pub -F docker-to-fc/ssh-keys/ssh-config root@${VM_IP}"
    mkdir -p tmp
    rm -f tmp/*

    local empty_fs=empty.ext4
    if [[ ! -f $empty_fs ]]; then
        dd if=/dev/zero of="${empty_fs}" bs=1M count=1024
        mkfs.ext4 "${empty_fs}"
    fi

    local last_idx=$(bc <<< "$num - 1")
    for id in $(seq 0 $last_idx); do
        local add_drive=fc-${id}.ext4
        local add_drive2=fc-${id}-2.ext4
        rm -f $add_drive.ext4 $add_drive2.ext4
        cp ${empty_fs} ${add_drive}
        cp ${empty_fs} ${add_drive2}
    done

    declare -A ncpus
    if [[ $cpubudget = "up" ]]; then
        ncpus+=( ["mobilenetv2"]=1 ["resnet50"]=1 ["ssdmobilenetv2"]=1 ["ssdresnet50v1"]=2 ["smallbert"]=1 ["talkingheads"]=2 )
    elif [[ $cpubudget = "down" ]]; then
        ncpus+=( ["mobilenetv2"]=2 ["resnet50"]=2 ["ssdmobilenetv2"]=2 ["ssdresnet50v1"]=2 ["smallbert"]=2 ["talkingheads"]=2 )
    fi
    declare -A memory
    memory+=( ["mobilenetv2"]=410 ["resnet50"]=1024 ["ssdmobilenetv2"]=1024 ["ssdresnet50v1"]=1434 ["smallbert"]=1024 ["talkingheads"]=2355 )


    for id in $(seq 0 $last_idx); do
        local add_drive=fc-${id}.ext4
        local add_drive2=fc-${id}-2.ext4
        TAP_DEV=$(./util_ipam.sh -t $id)
        TAP_IP=$(./util_ipam.sh -h $id)
        VM_IP=$(./util_ipam.sh -v $id)
        VM_MASK=$(./util_ipam.sh -m $id)
        MAYBE_MAC="$(cat /sys/class/net/tap$id/address)"
        TAP_MAC="$(./util_ipam.sh -a $id)"
        ${FCROOT}/firectl/firectl \
            --firecracker-binary=${FCROOT}/firecracker \
            --kernel=docker-to-fc/ubuntu-vmlinux \
            --root-drive=docker-to-fc/ubuntu-${app}.ext4:ro \
            --kernel-opts="init=/bin/systemd noapic reboot=k panic=1 pci=off nomodules console=ttyS0 ip=$VM_IP::$TAP_IP:$VM_MASK:$TAP_DEV:eth0:off" \
            --tap-device=$TAP_DEV/$TAP_MAC \
            --add-drive="${add_drive}":rw \
            --add-drive="${add_drive2}":rw \
            --socket-path=tmp/fc-$id.sock \
            --ncpus=${ncpus[$app]} \
            --memory=${memory[$app]} &
            # --kernel-opts="init=/bin/systemd noapic reboot=k panic=1 pci=off nomodules console=ttyS0" \
    done
    print_info "Running ${app}, n=$num"
}

function run_multiple_fc_bootexp() {
    local cpubudget=$1
    local app=$2
    local num=$3
    # sudo setfacl -m u:${USER}:rw /dev/kvm
    # [ -r /dev/kvm ] && [ -w /dev/kvm ] && echo "KVM Access OK" || echo "KVM Access FAIL"

    # echo MAC1=$MAC1
    # echo MAC2=$MAC2
    # exit

    # SSH="ssh -i docker-to-fc/ssh-keys/id_rsa.pub -F docker-to-fc/ssh-keys/ssh-config root@${VM_IP}"
    mkdir -p tmp
    rm -f tmp/*

    local empty_fs=empty.ext4
    if [[ ! -f $empty_fs ]]; then
        dd if=/dev/zero of="${empty_fs}" bs=1M count=1024
        mkfs.ext4 "${empty_fs}"
    fi

    local last_idx=$(bc <<< "$num - 1")
    for id in $(seq 0 $last_idx); do
        local add_drive=fc-${id}.ext4
        local add_drive2=fc-${id}-2.ext4
        rm -f $add_drive.ext4 $add_drive2.ext4
        cp ${empty_fs} ${add_drive}
        cp ${empty_fs} ${add_drive2}
    done

    declare -A ncpus
    if [[ $cpubudget = "up" ]]; then
        ncpus+=( ["mobilenetv2"]=1 ["resnet50"]=1 ["ssdmobilenetv2"]=1 ["ssdresnet50v1"]=2 ["smallbert"]=1 ["talkingheads"]=2 )
    elif [[ $cpubudget = "down" ]]; then
        ncpus+=( ["mobilenetv2"]=2 ["resnet50"]=2 ["ssdmobilenetv2"]=2 ["ssdresnet50v1"]=2 ["smallbert"]=2 ["talkingheads"]=2 )
    fi
    declare -A memory
    memory+=( ["mobilenetv2"]=410 ["resnet50"]=1024 ["ssdmobilenetv2"]=1024 ["ssdresnet50v1"]=1434 ["smallbert"]=1024 ["talkingheads"]=2355 )


    for id in $(seq 0 $last_idx); do
        local add_drive=fc-${id}.ext4
        local add_drive2=fc-${id}-2.ext4
        TAP_DEV=$(./util_ipam.sh -t $id)
        TAP_IP=$(./util_ipam.sh -h $id)
        VM_IP=$(./util_ipam.sh -v $id)
        VM_MASK=$(./util_ipam.sh -m $id)
        MAYBE_MAC="$(cat /sys/class/net/tap$id/address)"
        TAP_MAC="$(./util_ipam.sh -a $id)"
        i=$(( id+1 ))
        echo [parse/boot/${app%_*}/fc/$i/init/s] $(date +%s%6N)
        ${FCROOT}/firectl/firectl \
            --firecracker-binary=${FCROOT}/firecracker \
            --kernel=docker-to-fc/ubuntu-vmlinux \
            --root-drive=docker-to-fc/ubuntu-${app}.ext4:ro \
            --kernel-opts="init=/bin/systemd noapic reboot=k panic=1 pci=off nomodules console=ttyS0 ip=$VM_IP::$TAP_IP:$VM_MASK:$TAP_DEV:eth0:off" \
            --tap-device=$TAP_DEV/$TAP_MAC \
            --add-drive="${add_drive}":rw \
            --add-drive="${add_drive2}":rw \
            --socket-path=tmp/fc-$id.sock \
            --ncpus=${ncpus[$app]} \
            --memory=${memory[$app]} &
            # --kernel-opts="init=/bin/systemd noapic reboot=k panic=1 pci=off nomodules console=ttyS0" \
    done
    print_info "Running ${app}, n=$num"
}

function experiment() {
    local apps=(mobilenetv2 resnet50 smallbert ssdmobilenetv2 ssdresnet50v1 smallbert talkingheads)
    turnoff_multi $n > /dev/null 2>&1
    mkdir -p tmp
    
    for app in ${apps[@]}; do
        for n in $(seq 10); do
        # for n in 1 3 5 10 15 20; do
            echo app=$app, n=$n/20, iter=10

            for i in $(seq 5); do
                local ssh_pids=()
                sleep 3
                multi_run up $app $n > /dev/null 2>&1 &
                sleep $(bc <<< "10 + 5 * $n")
                local last_idx=$(( n - 1 ))
                for id in $(seq 0 $last_idx); do
                    ID=$id bash config_by_misun.sh ssh-command "cd ${app} && python3 app.monolithic.fc.py" > tmp/${app}_${id}.log 2>&1 &
                    ssh_pids+=($!)
                    sleep 1.5
                done
                wait ${ssh_pids[@]}
                turnoff_multi $n > /dev/null 2>&1
                for id in $(seq 0 $last_idx); do
                    cat tmp/${app}_${id}.log | grep 'inference_time'
                done
            done

            for i in $(seq 5); do
                local ssh_pids=()
                sleep 3
                multi_run down $app $n > /dev/null 2>&1 &
                sleep $(bc <<< "10 + 5 * $n")
                local last_idx=$(( n - 1 ))
                for id in $(seq 0 $last_idx); do
                    ID=$id bash config_by_misun.sh ssh-command "cd ${app} && python3 app.monolithic.fc.py" > tmp/${app}_${id}.log 2>&1 &
                    ssh_pids+=($!)
                    sleep 1.5
                done
                wait ${ssh_pids[@]}
                turnoff_multi $n > /dev/null 2>&1
                for id in $(seq 0 $last_idx); do
                    cat tmp/${app}_${id}.log  | grep 'inference_time'
                done
            done
        done
    done
}

function boottime() {
    local apps=(mobilenetv2 resnet50 ssdmobilenetv2 ssdresnet50v1 smallbert talkingheads)
    # local apps=(ssdresnet50v1 talkingheads)
    turnoff_multi $n > /dev/null 2>&1
    mkdir -p tmp
    
    for app in ${apps[@]}; do
        # for n in 1; do
        echo "[parse/header] CURRENT APPLICATION=$app"
        for n in 1 5 10 20; do
            echo "[parse/header] $app-pocket n=$n, i=10"

            # for i in $(seq 1); do
            for i in $(seq 1 5); do
                local ssh_pids=()
                sleep 3
                multi_run up $app $n > /dev/null 2>&1 &
                sleep $(bc <<< "10 + 5 * $n")
                local last_idx=$(( n - 1 ))
                for id in $(seq 0 $last_idx); do
                    id2=$(( id + 1 > n ? n : id + 1))
                    ID=$id bash config_by_misun.sh ssh-command "export CONTAINER_ID=$id2 && echo [parse/boot/${app%_*}/fc/$id2/init] \$(systemd-analyze | head -1 | awk '{ print \$10 }' | sed 's/s//g') \$(systemd-analyze | grep graphic | awk '{ print \$4 }' | sed 's/[sm]//g') && cd ${app} && echo -n '[parse/boot/${app%_*}/fc/$id2/boot] ' && date +%s%6N && python3 app.monolithic.fc.boot.py" > tmp/${app}_${id}.log 2>&1 &
                    # ID=$id bash config_by_misun.sh ssh-command "echo [parse/boot/${app%_*}/fc/$i/init] $(systemd-analyze | head -1 | awk '{ print $10 }' | sed 's/s//g'), $(systemd-analyze | grep graphic | awk '{ print $4 }' | sed 's/s//g') && cd ${app} && echo -n '[parse/boot/${app%_*}/fc/$i/boot] ' && date +%s%6N && python3 app.monolithic.fc.boot.py" > tmp/${app}_${id}.log 2>&1 &
                    # ID=$id bash config_by_misun.sh ssh-command "a=($(last boot)) && date -d \"$(echo \${a[@]:2})\" '+%s%6N' && cd ${app} && echo -n '[parse/boot/${app%_*}/fc/$i/boot] ' && date +%s%6N && python3 app.monolithic.fc.boot.py" > tmp/${app}_${id}.log 2>&1 &
                    ssh_pids+=($!)
                    sleep 1.5
                done
                wait ${ssh_pids[@]}
                turnoff_multi $n > /dev/null 2>&1
                for id in $(seq 0 $last_idx); do
                    cat tmp/${app}_${id}.log | grep -E '\[parse/boot|\[parse/graph'
                done
            done

            for i in $(seq 6 10); do
                local ssh_pids=()
                sleep 3
                multi_run down $app $n > /dev/null 2>&1 &
                sleep $(bc <<< "10 + 5 * $n")
                local last_idx=$(( n - 1 ))
                for id in $(seq 0 $last_idx); do
                    id2=$(( id + 1 > n ? n : id + 1))
                    ID=$id bash config_by_misun.sh ssh-command "export CONTAINER_ID=$id2 && echo [parse/boot/${app%_*}/fc/$id2/init] \$(systemd-analyze | head -1 | awk '{ print \$10 }' | sed 's/s//g') \$(systemd-analyze | grep graphic | awk '{ print \$4 }' | sed 's/[ms]//g') && cd ${app} && echo -n '[parse/boot/${app%_*}/fc/$id2/boot] ' && date +%s%6N && python3 app.monolithic.fc.boot.py" > tmp/${app}_${id}.log 2>&1 &
                    ssh_pids+=($!)
                    sleep 1.5
                done
                wait ${ssh_pids[@]}
                turnoff_multi $n > /dev/null 2>&1
                for id in $(seq 0 $last_idx); do
                    cat tmp/${app}_${id}.log  | grep -E '\[parse/boot|\[parse/graph'
                done
            done
        done
    done
}

function turnoff_multi() {
    local num=$(bc <<< "$1 - 1")
    for id in $(seq 0 $num); do
        curl --unix-socket tmp/fc-$id.sock -i \
            -X PUT 'http://localhost/actions' \
            -d '{ "action_type": "SendCtrlAltDel" }'
        
    done
    for id in $(seq 0 $num); do
        rm -f tmp/fc-$id.sock
    done
}

function init_multiple_network() {
    # code from: https://github.com/firecracker-microvm/nsdi2020-data/blob/master/scripts/00_setup_host.sh
    local num=$1
    chmod +x ./util_ipam.sh

    # Number of Tap devices to create
    NUM_TAPS=1

    ##
    ## Configure the host
    ##
    ## - Configure packet forwarding
    ## - Avoid "nf_conntrack: table full, dropping packet"
    ## - Avoid "neighbour: arp_cache: neighbor table overflow!"
    ##
    sudo modprobe kvm_intel
    sudo sysctl -w net.ipv4.conf.all.forwarding=1

    # sudo sysctl -w net.ipv4.netfilter.ip_conntrack_max=99999999
    sudo sysctl -w net.netfilter.nf_conntrack_max=99999999
    sudo sysctl -w net.nf_conntrack_max=99999999
    sudo sysctl -w net.netfilter.nf_conntrack_max=99999999

    sudo sysctl -w net.ipv4.neigh.default.gc_thresh1=1024
    sudo sysctl -w net.ipv4.neigh.default.gc_thresh2=2048
    sudo sysctl -w net.ipv4.neigh.default.gc_thresh3=4096

    ##
    ## Create and configure network taps (delete existing ones)
    ##

    MASK=$(./util_ipam.sh -m)
    PREFIX_LEN=$(./util_ipam.sh -l)

    for ((i=0; i<num; i++)); do

        DEV=$(./util_ipam.sh -t $i)
        IP=$(./util_ipam.sh -h $i)

        sudo ip link del "$DEV" 2> /dev/null || true
        sudo ip tuntap add dev "$DEV" mode tap

        sudo sysctl -w net.ipv4.conf.${DEV}.proxy_arp=1 > /dev/null
        sudo sysctl -w net.ipv6.conf.${DEV}.disable_ipv6=1 > /dev/null

        sudo ip addr add "${IP}${PREFIX_LEN}" dev "$DEV"
        sudo ip link set dev "$DEV" up

        sudo sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"
        sudo iptables -t nat -A POSTROUTING -o eno1 -j MASQUERADE # eno0 is just the name of interface.. if you're using eth0 you should refer that one..
        sudo iptables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
        sudo iptables -A FORWARD -i $DEV -o eno1 -j ACCEPT
    done
}

function fin_multiple_network() {
    local num=$1
    for ((i=0; i<num; i++)); do

        DEV=$(./util_ipam.sh -t $i)
        IP=$(./util_ipam.sh -h $i)

        sudo ip link del "$DEV" 2> /dev/null || true
        sudo ip tuntap del "$DEV"
    done
    # sudo iptables -F
    # sudo sh -c "echo 0 > /proc/sys/net/ipv4/ip_forward" # usually the default
}

function push_images() {
    local device=cpu
    local docker_hub_id=misunpark
    docker login
    for app in mobilenetv2 resnet50 ssdmobilenetv2 ssdresnet50v1 smallbert talkingheads; do
        local local_image=pocket-$app-$device-monolithic
        docker tag $local_image ${docker_hub_id}/${local_image}
        docker push ${docker_hub_id}/${local_image}
    done
}

function network_init() {
    # code from: https://github.com/firecracker-microvm/nsdi2020-data/blob/master/scripts/00_setup_host.sh
    chmod +x ./util_ipam.sh

    # Number of Tap devices to create
    NUM_TAPS=1

    ##
    ## Configure the host
    ##
    ## - Configure packet forwarding
    ## - Avoid "nf_conntrack: table full, dropping packet"
    ## - Avoid "neighbour: arp_cache: neighbor table overflow!"
    ##
    sudo modprobe kvm_intel
    sudo sysctl -w net.ipv4.conf.all.forwarding=1

    # sudo sysctl -w net.ipv4.netfilter.ip_conntrack_max=99999999
    sudo sysctl -w net.netfilter.nf_conntrack_max=99999999
    sudo sysctl -w net.nf_conntrack_max=99999999
    sudo sysctl -w net.netfilter.nf_conntrack_max=99999999

    sudo sysctl -w net.ipv4.neigh.default.gc_thresh1=1024
    sudo sysctl -w net.ipv4.neigh.default.gc_thresh2=2048
    sudo sysctl -w net.ipv4.neigh.default.gc_thresh3=4096

    ##
    ## Create and configure network taps (delete existing ones)
    ##

    MASK=$(./util_ipam.sh -m)
    PREFIX_LEN=$(./util_ipam.sh -l)

    for ((i=0; i<NUM_TAPS; i++)); do

        DEV=$(./util_ipam.sh -t $i)
        IP=$(./util_ipam.sh -h $i)

        sudo ip link del "$DEV" 2> /dev/null || true
        sudo ip tuntap add dev "$DEV" mode tap

        sudo sysctl -w net.ipv4.conf.${DEV}.proxy_arp=1 > /dev/null
        sudo sysctl -w net.ipv6.conf.${DEV}.disable_ipv6=1 > /dev/null

        sudo ip addr add "${IP}${PREFIX_LEN}" dev "$DEV"
        sudo ip link set dev "$DEV" up

        sudo sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"
        sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
        sudo iptables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
        sudo iptables -A FORWARD -i $DEV -o eth0 -j ACCEPT
    done
}

function network_run() {
    ID=0
    TAP_DEV=$(./util_ipam.sh -t $ID)
    TAP_IP=$(./util_ipam.sh -h $ID)
    VM_IP=$(./util_ipam.sh -v $ID)
    VM_MASK=$(./util_ipam.sh -m $ID)
    MAYBE_MAC="$(cat /sys/class/net/tap$ID/address)"
    TAP_MAC="$(./util_ipam.sh -a $ID)"

    # echo MAC1=$MAC1
    # echo MAC2=$MAC2
    # exit

    SSH="ssh -i docker-to-fc/ssh-keys/id_rsa.pub -F docker-to-fc/ssh-keys/ssh-config root@${VM_IP}"

    apps=(mobilenetv2)
    # apps=(mobilenetv2 resnet50 smallbert ssdmobilenetv2 ssdresnet50v1 smallbert talkingheads)
    for app in ${apps[@]}; do
        print_info "Running ${app}"
        ${FCROOT}/firectl/firectl \
            --firecracker-binary=${FCROOT}/firecracker \
            --kernel=docker-to-fc/ubuntu-vmlinux \
            --root-drive=docker-to-fc/ubuntu-${app}.ext4:ro \
            --kernel-opts="init=/bin/systemd noapic reboot=k panic=1 pci=off nomodules console=ttyS0 ip=$VM_IP::$TAP_IP:$VM_MASK:$TAP_DEV:eth0:off" \
            --tap-device=$TAP_DEV/$TAP_MAC \
            --debug
            # --kernel-opts="init=/bin/systemd noapic reboot=k panic=1 pci=off nomodules console=ttyS0" \
    done
}

function network_fin() {
    NUM_TAPS=1
    for ((i=0; i<NUM_TAPS; i++)); do

        DEV=$(./util_ipam.sh -t $i)
        IP=$(./util_ipam.sh -h $i)

        sudo ip link del "$DEV" 2> /dev/null || true
        sudo ip tuntap del "$DEV"
    done
}


_BOLD="\e[1m"
_DIM="\e[2m"
_RED="\e[31m"
_LYELLOW="\e[93m"
_LGREEN="\e[92m"
_LCYAN="\e[96m"
_LMAGENTA="\e[95m"
_RESET="\e[0m"


function print_error() {
    local message=$1
    echo -e "${_BOLD}${_RED}[ERROR]${_RESET} ${message}${_RESET}"

}

function print_warning() {
    local message=$1
    echo -e "${_BOLD}${_LYELLOW}[WARN]${_RESET} ${message}${_RESET}"

}

function print_info() {
    local message=$1
    echo -e "${_BOLD}${_LGREEN}[INFO]${_RESET} ${message}${_RESET}"

}

function print_debug() {
    local message=$1
    echo -e "${_BOLD}${_LCYAN}[DEBUG]${_RESET} ${message}${_RESET}"

}

main "$@"; exit