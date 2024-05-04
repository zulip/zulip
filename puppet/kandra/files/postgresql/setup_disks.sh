#!/bin/bash
set -x
set -e

set -o pipefail

LOCALDISK=$(
    nvme list -o json \
        | jq -r '.Devices[] | select(.ModelNumber | contains("Instance Storage")) | .DevicePath' \
        | head -n1
)

if [ -z "$LOCALDISK" ]; then
    echo "No instance storage found!"
    nvme list
    exit 1
fi

if ! grep -q "$LOCALDISK" /etc/fstab; then
    echo "$LOCALDISK   /srv/data  xfs    nofail,noatime 1 1" >>/etc/fstab
fi

if [ ! -d /srv/data ]; then
    mkdir /srv/data
fi

if ! mountpoint -q /srv/data; then
    mkfs.xfs "$LOCALDISK"
    mount /srv/data
fi

if [ ! -L /var/lib/postgresql ]; then
    service postgresql stop
    if [ -e /var/lib/postgresql ]; then
        mv /var/lib/postgresql "/root/postgresql-data-$(date +'%m-%d-%Y-%T')"
    fi
    ln -s /srv/data/postgresql/ /var/lib
fi

if [ ! -e "/srv/data/postgresql" ]; then
    service postgresql stop
    mkdir "/srv/data/postgresql"
    chown postgres:postgres /srv/data/postgresql
fi
