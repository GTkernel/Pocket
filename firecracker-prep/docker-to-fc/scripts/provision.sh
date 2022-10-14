#! /bin/bash
set -ex

# dpkg -i /mnt/workspace/linux*.deb
dpkg -i /workspace/linux*.deb

echo 'ubuntu-bionic' > /etc/hostname
echo '127.0.0.1     localhost' >> /etc/hosts
echo 'nameserver     8.8.8.8' >> /etc/resolv.conf
echo '/dev/vdb      /tmp    ext4    defaults     0     0' >> /etc/fstab
echo '/dev/vdc      /var    ext4    defaults     0     0' >> /etc/fstab
rm -rf /var/*
rm -rf /tmp/* /.*dockerenv /tmp-*
passwd -d root

# cat <<EOF > /root/init-network.sh
# IPADDR=$(ifconfig eth0 | grep 'inet' | head -n 1 | cut -d' ' -f10)
# echo 'init-net done' > /root/init-net.txt
# ip addr add ${IPADDR}/30 dev eth0
# ip link set eth0 up
# ip route add default via $IPADDR && echo "nameserver 8.8.8.8" > /etc/resolv.conf
# EOF

# echo '@reboot root /root/init-network.sh' >> /etc/cron.d

mkdir /etc/systemd/system/serial-getty@ttyS0.service.d/
cat <<EOF > /etc/systemd/system/serial-getty@ttyS0.service.d/autologin.conf
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root -o '-p -- \\u' --keep-baud 115200,38400,9600 %I $TERM
EOF

# cat <<EOF > /etc/netplan/99_config.yaml
# network:
#   version: 2
#   renderer: networkd
#   ethernets:
#     eth0:
#       dhcp4: true
# EOF
# netplan generate
