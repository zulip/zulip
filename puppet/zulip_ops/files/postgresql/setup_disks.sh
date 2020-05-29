#!/bin/sh

LOCALDISK=/dev/nvme0n1

mkfs.xfs $LOCALDISK

echo "$LOCALDISK   /srv  xfs    nofail,noatime 1 1" >> /etc/fstab
mount /srv

# TODO use systemctl instead of pg_ctlcluster on CentOS
pg_ctlcluster 9.5 main stop
mv /var/lib/postgresql /srv
ln -s /srv/postgresql/ /var/lib

# TODO use systemctl instead of pg_ctlcluster on CentOS
pg_ctlcluster 9.5 main start
