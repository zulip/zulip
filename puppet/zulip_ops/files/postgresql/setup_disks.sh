#!/bin/sh
set -x
set -e

# This file only exists on the server, ignore its non-existence locally
# shellcheck disable=SC1091
. "/sys/dev/block/259:0/uevent"

LOCALDISK="/dev/$DEVNAME"
if ! grep -q "$LOCALDISK" /etc/fstab; then
    echo "$LOCALDISK   /srv  xfs    nofail,noatime 1 1" >>/etc/fstab
fi

if ! mountpoint -q /srv; then
    mkfs.xfs "$LOCALDISK"
    # Move any existing files/directories out of the way
    TMPDIR=$(mktemp -d)
    mv /srv/* "$TMPDIR"
    mount /srv
    mv "$TMPDIR/"* /srv
    rmdir "$TMPDIR"
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
