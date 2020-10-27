#!/bin/sh
set -x
set -e

LOCALDISK=/dev/nvme0n1

if ! grep -q $LOCALDISK /etc/fstab; then
    echo "$LOCALDISK   /srv  xfs    nofail,noatime 1 1" >>/etc/fstab
fi

if ! mountpoint -q /srv; then
    mkfs.xfs $LOCALDISK
    mount /srv
fi

if [ ! -L /var/lib/postgresql ]; then
    service postgresql stop
    if [ -e /var/lib/postgresql ]; then
        mv /var/lib/postgresql "/root/postgresql-data-$(date +'%m-%d-%Y-%T')"
    fi
    ln -s /srv/postgresql/ /var/lib
fi

if [ ! -e "/srv/postgresql" ]; then
    service postgresql stop
    mkdir "/srv/postgresql"
    chown postgres:postgres /srv/postgresql
fi
