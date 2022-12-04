FROM ubuntu:18.04

ENV DEBIAN_FRONTEND noninteractive
ENV KERNEL_SOURCE_VERSION 5.3.0

WORKDIR /root

# RUN rm -rf /etc/apt/sources.list.d
# RUN apt upgrade
RUN apt update && \
	apt install -y \
		curl debootstrap docker.io \
		build-essential kernel-package bison rsync rsyslog fakeroot \
		linux-source-$KERNEL_SOURCE_VERSION bc kmod cpio flex cpio \
    	libncurses5-dev libelf-dev libssl-dev && \
	tar xvf /usr/src/linux-source-$KERNEL_SOURCE_VERSION.tar.* && \
	rm -rf /var/lib/apt/lists/*