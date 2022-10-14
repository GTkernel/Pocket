#!/usr/bin/env bash
FCROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

function main( ){
    COMMAND=$1
    case $COMMAND in
        install)
            install
            ;;
        network-test)
            network_test
            ;;
        experiment)
            experiment
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
    # print_info "Setting FireCracker.."
    # print_info "Setting up KVM access.."
    # print_info "sudo access is required."

    # sudo setfacl -m u:${USER}:rw /dev/kvm
    # [ -r /dev/kvm ] && [ -w /dev/kvm ] && echo "KVM Access OK" || echo "KVM Access FAIL"
    
    # print_info "Getting the FireCracker Binary.."
    # # https://arun-gupta.github.io/firecracker-getting-started/
    # release_url="https://github.com/firecracker-microvm/firecracker/releases"
    # # latest=$(basename $(curl -fsSLI -o /dev/null -w  %{url_effective} ${release_url}/latest))
    # version=v1.1.0
    # arch=`uname -m`
    # curl -L ${release_url}/download/${version}/firecracker-${version}-${arch}.tgz | tar -xz
    # mv release-${version}-$(uname -m)/firecracker-${version}-$(uname -m) "${FCROOT}"/firecracker

    # # getting_default_kernel_fs
    # install_firectl
    # # test_firectl_minimal
    # # # custom_rootfs_and_kernel 
    custom_rootfs_and_kernel
    # test_firectl_all
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
    local SSH="ssh -i docker-to-fc/ssh-keys/id_rsa -F docker-to-fc/ssh-keys/ssh-config root@${VM_IP}"
    ${SSH} $command
}

function install_firectl() {
    # https://github.com/firecracker-microvm/firectl
    # https://s8sg.medium.com/quick-start-with-firecracker-and-firectl-in-ubuntu-f58aeedae04b
    # https://gruchalski.com/posts/2021-02-14-firecracker-vmm-with-additional-disks/
    git clone https://github.com/firecracker-microvm/firectl.git
    cd firectl
    make build-in-docker
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
    # push_images
    # docker build -t kernel-rootfs-builder --no-cache .

    apps=(mobilenetv2)
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
        # read -rsp $'Press any key to continue...\n' -n1 key
        # print_info "Running ${app}"
        # ${FCROOT}/firectl/firectl \
        #     --firecracker-binary=${FCROOT}/firecracker \
        #     --kernel=ubuntu-vmlinux \
        #     --root-drive=ubuntu-${app}.ext4 \
        #     --kernel-opts="init=/bin/systemd noapic reboot=k panic=1 pci=off nomodules console=ttyS0"
    done
    cd -
}

function dry_run() {
    # git clone https://github.com/anyfiddle/firecracker-rootfs-builder.git
    # cd docker-to-fc

    apps=(mobilenetv2)
    # apps=(mobilenetv2 resnet50 smallbert ssdmobilenetv2 ssdresnet50v1 smallbert talkingheads)
    for app in ${apps[@]}; do
        print_info "Running ${app}"
        ${FCROOT}/firectl/firectl \
            --firecracker-binary=${FCROOT}/firecracker \
            --kernel=docker-to-fc/ubuntu-vmlinux \
            --root-drive=docker-to-fc/ubuntu-${app}.ext4:ro \
            --kernel-opts="init=/bin/systemd noapic reboot=k panic=1 pci=off nomodules console=ttyS0"
    done
    # cd - > /dev/null 2>&1
}

function multi_run() {
    # bash config_by_misun.sh ssh-command
    # for i in $(seq)
    local app=$1
    local num=$2
    fin_multiple_network $num
    init_multiple_network $num

    sleep 5

    run_multiple_fc $app $num
    # fin_multiple_network $num
}

function run_multiple_fc() {
    local app=$1
    local num=$2
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
            --socket-path=tmp/fc-$id.sock
            # --kernel-opts="init=/bin/systemd noapic reboot=k panic=1 pci=off nomodules console=ttyS0" \
    done
    print_info "Running ${app}, n=$num"
}

function experiment() {
    local app=mobilenetv2
    local num=1
    local ssh_pids=()
    turnoff_multi $num > /dev/null 2>&1
    sleep 3
    multi_run $app $num
    sleep 25
    mkdir -p tmp
    local last_idx=$(( num - 1 ))
    read
    for id in $(seq 0 $last_idx); do
        echo id=$id
        ID=$id bash config_by_misun.sh ssh-command echo hello world #"cd ${app} && python3 app.monolithic.py" #> tmp/${app}_${id}.log 2>&1 &
        ssh_pids+=($!)
        sleep 1.5
    done
    echo ${ssh_pids[@]}

    wait ${ssh_pids[@]}
    # echo wait
    # wait
    # echo wait done
    # turnoff_multi $num
    # for i in $(seq $num); do
    #     cat tmp/${app}_${id}.log #| grep 'inference_time'
    # done


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
        sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
        sudo iptables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
        sudo iptables -A FORWARD -i $DEV -o eno0 -j ACCEPT
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
    sudo iptables -F
    sudo sh -c "echo 0 > /proc/sys/net/ipv4/ip_forward" # usually the default
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