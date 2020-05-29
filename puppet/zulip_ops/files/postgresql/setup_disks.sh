#!/bin/sh

LOCALDISK=/dev/nvme0n1

mkfs.xfs $LOCALDISK

echo "$LOCALDISK   /srv  xfs    nofail,noatime 1 1" >> /etc/fstab
mount /srv

service postgresql stop
mv /var/lib/postgresql /srv
ln -s /srv/postgresql/ /var/lib

service postgresql start
