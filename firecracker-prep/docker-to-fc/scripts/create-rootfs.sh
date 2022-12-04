#!/bin/bash
set -ex

image_tag=$1
pwd=$2
app=$3
dir=$4

rm -rf /workspace/*
cp -R /root/linux-source-$KERNEL_SOURCE_VERSION /workspace/linux-source-$KERNEL_SOURCE_VERSION
cp /scripts/.config /workspace/linux-source-$KERNEL_SOURCE_VERSION
cd /workspace/linux-source-$KERNEL_SOURCE_VERSION
yes '' | make oldconfig
make -j $(nproc) deb-pkg
# ls -al /workspace/linux-source-$KERNEL_SOURCE_VERSION
# ls -al /workspace
cd /workspace

rm -rf /output/*

cp /workspace/linux-source-$KERNEL_SOURCE_VERSION/vmlinux /output/vmlinux
cp /workspace/linux-source-$KERNEL_SOURCE_VERSION/.config /output/config

truncate -s 30G /output/image.ext4
mkfs.ext4 /output/image.ext4


# mount --bind / /rootfs/mnt
# ls -al /rootfs
# ls -al /rootfs/mnt
# ls -al /rootfs/mnt/usr/local/lib/python3.6/dist-packages
# chroot /rootfs /bin/bash /mnt/scripts/provision.sh

# umount /rootfs/mnt
# umount /rootfs

# cd /output
# tar czvf ubuntu-bionic.tar.gz image.ext4 vmlinux config
# cd /

rootFsMount=/rootfs
prepareScript=/scripts/provision.sh
ls -al /scripts
# docker run ${image_tag} bash -cx "ls -al /tmp-scripts"
# docker run --volume="$pwd"/scripts:/tmp-scripts ${image_tag} bash -cx "ls -al /tmp-scripts"

docker container rm filesystem || true
docker run \
    --volume="$pwd"/scripts:/tmp-scripts \
    --volume="$pwd"/workspace:/tmp-workspace \
    --volume="$pwd"/ssh-keys:/ssh-keys \
    --volume="$pwd"/../../resources/models:/tmp-models \
    --volume="$pwd"/../../resources/coco/val2017:/tmp-coco2017 \
    --volume="$pwd"/../../applications/${dir}:/tmp-${app} \
    --name filesystem ${image_tag} \
    bash -cx "apt-get update -y && apt install -y net-tools openssh-server && mkdir /scripts > /dev/null 2>&1 && touch /scripts/provision.sh > /dev/null 2>&1 && cat /tmp-scripts/provision.sh > /scripts/provision.sh && mkdir /workspace && cp -R /tmp-workspace/* /workspace && mkdir -p /root/.ssh && cp /ssh-keys/* /root/.ssh && cat /root/.ssh/id_rsa.pub >> /root/.ssh/authorized_keys && cp -R /tmp-models /models && cp -R /tmp-coco2017 /root/coco2017 && cp -R /tmp-${app} /root/${app} && echo 'PasswordAuthentication no' >> /etc/ssh/sshd_config && echo 'PermitRootLogin without-password' >> /etc/ssh/sshd_config"

sleep 5
docker export filesystem > rootfs.tar

mkdir /rootfs
mount /output/image.ext4 /rootfs
debootstrap --include openssh-server,unzip,rsync,apt,netplan.io,nano \
    bionic /rootfs http://archive.ubuntu.com/ubuntu/

tar -C ${rootFsMount} -xf rootfs.tar

# ls -al /rootfs/
# ls -al /rootfs/usr/local/lib/python3.6/dist-packages
# ls -al /rootfs/scripts/

echo "Change to mounted rootfs using chroot"
mount -t proc /proc ${rootFsMount}/proc/
mount -t sysfs /sys ${rootFsMount}/sys/
mount -o bind /dev ${rootFsMount}/dev/

# Execute prepare server
echo "Customizing image with prepare.sh"
# chroot ${rootFsMount} /bin/sh pwd
chroot ${rootFsMount} /bin/sh ${prepareScript}
# chroot ${rootFsMount} /bin/sh ${prepareScript}
# rm ${rootFsMount}${prepareScript}

echo "Unmounting"
umount ${rootFsMount}/dev
umount ${rootFsMount}/proc
umount ${rootFsMount}/sys

