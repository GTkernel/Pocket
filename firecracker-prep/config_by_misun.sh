#!/usr/bin/env bash
FCROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

function main( ){
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

    # getting_default_kernel_fs
    # install_firectl
    # test_firectl_minimal
    # # custom_rootfs_and_kernel 
    custom_rootfs_and_kernel2 
}

function install_firectl() {
    # https://github.com/firecracker-microvm/firectl
    # https://s8sg.medium.com/quick-start-with-firecracker-and-firectl-in-ubuntu-f58aeedae04b
    git clone https://github.com/firecracker-microvm/firectl.git
    cd firectl
    make build-in-docker
    # INSTALLPATH=${FCROOT}/firectl make install
}

function test_firectl_minimal() {
    ./firectl/firectl \
        --firecracker-binary=${FCROOT}/firecracker \
        --kernel=hello-vmlinux.bin \
        --root-drive=hello-rootfs.ext4 \
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
    # # https://github.com/firecracker-microvm/firecracker/blob/main/docs/rootfs-and-kernel-setup.md
    # # https://stackoverflow.com/questions/53938944/firecracker-microvm-how-to-create-custom-firecracker-microvm-and-file-system-im
    # # https://gruchalski.com/posts/2021-03-23-introducing-firebuild/
    print_info "Installing Firebuild"
    # install_firebuild

    print_info "Create VM Images"
    create_image
}

function custom_rootfs_and_kernel2() {
    # # https://happybear.medium.com/building-ubuntu-20-04-root-filesystem-for-firecracker-e3f4267e58cc
    # # https://github.com/bkleiner/ubuntu-firecracker
    # # https://medium.com/@Pawlrus/making-a-custom-microvm-for-aws-firecracker-f22c761a6ceb
    # # https://github.com/anyfiddle/firecracker-rootfs-builder.git

    git clone https://github.com/bkleiner/ubuntu-firecracker.git
    cd ubuntu-firecracker
    
    # docker build -t ubuntu-firecracker .
    # docker run --privileged -it --rm -v $(pwd)/output:/output ubuntu-firecracker

    cp -R ${FCROOT}/../resources/obj_det_sample_img ${FCROOT}/ubuntu-firecracker/obj_det_sample_img
    cp ${FCROOT}/dockerfiles/* ${FCROOT}/ubuntu-firecracker

    # apps=(mobilenetv2)
    apps=(mobilenetv2 resnet50 smallbert ssdmobilenetv2 ssdresnet50v1 smallbert talkingheads)
    for app in ${apps[@]}; do
        docker image rm -f fc-${app}
        docker build -t fc-${app} -f Dockerfile.${app} --cpu-shares=24 .
    done

    # Clean up
    rm -rf ${FCROOT}/ubuntu-firecracker/obj_det_sample_img
    rm -rf ${FCROOT}/ubuntu-firecracker/Dockerfile.{mobilenetv2,resnet50,smallbert,ssdmobilenetv2,ssdresnet50v1,smallbert,talkingheads}
    rm -rf tmp
}

function install_firebuild() {
    https://gruchalski.com/posts/2021-03-22-firebuild-prerequisites/
    install_golang
    install_cni_plugins
    create_cni_network_config
    build_firebuild
    print_warning "Put this command to make $GOPATH system-wide: \"echo \\\$GOPATH=\$GOPATH >> /etc/profile\""
}

function install_golang() {
    print_info "Build the rootfs using Firebuild.."
    print_info "Prerequisite: Install Golang first (https://go.dev/doc/install)"
    rm -rf ${FCROOT}/tmp/go; mkdir -p ${FCROOT}/tmp/go
    mkdir -p $HOME/dev/golang/{bin,src}

    wget -P ${FCROOT}/tmp/go https://go.dev/dl/go1.19.1.linux-amd64.tar.gz
    sudo bash -c "${FCROOT}/tmp/go && rm -rf /usr/local/go && tar -C /usr/local -xzf ${FCROOT}/tmp/go/go1.19.1.linux-amd64.tar.gz"

    print_warning "Add /usr/local/go/bin to \$PATH (export PATH=/usr/local/go/bin:\$PATH)"
    print_warning "Define \$GOPATH (export \$GOPATH=\$HOME/dev/golang)"
    print_info "Current \$PATH: $PATH, \$GOPATH: $GOPATH"
}

function install_cni_plugins() {
    sudo rm -rf /opt/cni/bin && sudo mkdir -p /opt/cni/bin
    curl -O -L https://github.com/containernetworking/plugins/releases/download/v0.9.1/cni-plugins-linux-amd64-v0.9.1.tgz
    rm -rf ${FCROOT}/tmp/cniplugins && mkdir -p ${FCROOT}/tmp/cniplugins
    mv cni-plugins-linux-amd64-v0.9.1.tgz ${FCROOT}/tmp/cniplugins
    sudo tar -C /opt/cni/bin -xzf ${FCROOT}/tmp/cniplugins/cni-plugins-linux-amd64-v0.9.1.tgz

    rm -rf $GOPATH/src/github.com/awslabs/tc-redirect-tap
    mkdir -p $GOPATH/src/github.com/awslabs/tc-redirect-tap
    cd $GOPATH/src/github.com/awslabs/tc-redirect-tap
    git clone https://github.com/awslabs/tc-redirect-tap.git .
    sudo make install
}

function create_cni_network_config() {
    sudo rm -rf /etc/cni/conf.d
    sudo mkdir -p /etc/cni/conf.d

    # sudo touch /etc/cni/conf.d/machines.conflist
    # sudo touch /etc/cni/conf.d/machines-builds.conflist
    # # ls /etc/cni/conf.d/machines.conflist
    # # ls /etc/cni/conf.d/machine-builds.conflist

sudo bash -c 'cat <<EOF > /etc/cni/conf.d/machines.conflist
{
    "name": "machines",
    "cniVersion": "0.4.0",
    "plugins": [
        {
            "type": "bridge",
            "name": "machines-bridge",
            "bridge": "machines0",
            "isDefaultGateway": true,
            "ipMasq": true,
            "hairpinMode": true,
            "ipam": {
                "type": "host-local",
                "subnet": "192.168.127.0/24",
                "resolvConf": "/etc/resolv.conf"
            }
        },
        {
            "type": "firewall"
        },
        {
            "type": "tc-redirect-tap"
        }
    ]
}
EOF'

sudo bash -c 'cat <<EOF > /etc/cni/conf.d/machine-builds.conflist
{
    "name": "machine-builds",
    "cniVersion": "0.4.0",
    "plugins": [
        {
            "type": "bridge",
            "name": "machine-builds-bridge",
            "bridge": "builds0",
            "isDefaultGateway": true,
            "ipMasq": true,
            "hairpinMode": true,
            "ipam": {
                "type": "host-local",
                "subnet": "192.168.128.0/24",
                "resolvConf": "/etc/resolv.conf"
            }
        },
        {
            "type": "firewall"
        },
        {
            "type": "tc-redirect-tap"
        }
    ]
}
EOF'
}

function build_firebuild() {
    mkdir -p $GOPATH/src/github.com/combust-labs/firebuild
    cd $GOPATH/src/github.com/combust-labs/firebuild
    git clone https://github.com/combust-labs/firebuild .
    go install
}


function create_image() {
    # create_firebuild_profile
    # create_vmlinux
    # create_baseos
    # push_images
    create_rootfs
}

function create_firebuild_profile() {
    local firecracker=${FCROOT}/firecracker
    local profile=standard

    sudo rm -rf /etc/firebuild/profiles/$profile

    # sudo rm -rf /firecracker/rootfs
    # sudo rm -rf /firecracker/vmlinux
    # sudo rm -rf /fc/jail
    # sudo rm -rf /fc/cache

    sudo mkdir -p /fc/rootfs
    sudo mkdir -p /fc/vmlinux
    sudo mkdir -p /fc/jail
    sudo mkdir -p /fc/cache

    print_debug "A profile specifies the location of resulting files"

    sudo $GOPATH/bin/firebuild profile-create \
        --profile=$profile \
        --binary-firecracker=$(readlink $firecracker) \
        --chroot-base=/fc/jail \
        --run-cache=/fc/cache \
        --storage-provider=directory \
        --storage-provider-property-string="rootfs-storage-root=/fc/rootfs" \
        --storage-provider-property-string="kernel-storage-root=/fc/vmlinux"
        # --binary-jailer=$(readlink /usr/bin/jailer) \
        # --binary-firecracker=$(readlink /usr/bin/firecracker) \
}

function create_vmlinux() {
    local kernel_version=v5.8

    mkdir -p /tmp/linux && cd /tmp/linux
    git clone https://github.com/torvalds/linux.git .
    git checkout ${kernel_version}
    wget -O .config https://raw.githubusercontent.com/combust-labs/firebuild/master/baseos/kernel/5.8.config
    make vmlinux -j24 # adapt to the number of cores you have

    mv /tmp/linux/vmlinux /fc/vmlinux/vmlinux-${kernel_version}

}

function create_baseos() {
    local device=cpu
    sudo rm -rf /fc/rootfs/_/ubuntu/18.04

    sudo $GOPATH/bin/firebuild baseos \
        --profile=standard \
        --dockerfile ${FCROOT}/baseos/Dockerfiles/ubuntu/18.04/Dockerfile \
        --tag=baseos/ubuntu:18.04
        # baseos/_/alpine/3.12/Dockerfile
        # --dockerfile ${FCROOT}/../applications/mobilenetv2/dockerfiles/${device}/Dockerfile.monolithic.perf
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

function create_rootfs() {
    sudo $GOPATH/bin/firebuild rootfs \
        --profile=standard \
        --docker-image=misunpark/pocket-mobilenetv2-cpu-monolithic:latest \
        --docker-image-base=ubuntu:18.04 \
        --cni-network-name=machine-builds \
        --vmlinux-id=vmlinux-v5.8 \
        --mem=512 \
        --tag=applications/mobilenetv2:0.1.0
    exit
    sudo $GOPATH/bin/firebuild rootfs \
        --profile=standard \
        --docker-image=misunpark/pocket-mobilenetv2-cpu-monolithic:latest \
        --docker-image-base=ubuntu:18.04 \
        --cni-network-name=machine-builds \
        --ssh-user=ubuntu \
        --vmlinux-id=vmlinux-v5.8 \
        --tag=applications/mobilenetv2:0.1.0
    # sudo $GOPATH/bin/firebuild rootfs \
    #     --profile=standard \
    #     --dockerfile=${FCROOT}/../applications/mobilenetv2/dockerfiles/${device}/Dockerfile.monolithic.perf \
    #     --cni-network-name=machine-builds \
    #     --ssh-user=ubuntu \
    #     --vmlinux-id=vmlinux-v5.8 \
    #     --tag=applications/mobilenetv2:0.1.0
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