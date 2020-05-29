#!/bin/sh
umount /mnt

LOCALDISK=/dev/nvme0n1

mkfs.xfs $LOCALDISK

echo "$LOCALDISK   /srv  xfs    nofail,noatime 1 1" >> /etc/fstab
mount /srv

# TODO use systemctl instead of pg_ctlcluster on CentOS
pg_ctlcluster 9.5 main stop
mv /var/lib/postgresql /srv
ln -s /srv/postgresql/ /var/lib

mv /tmp /srv
mkdir /tmp
mount --bind /srv/tmp /tmp
echo "/srv/tmp   /tmp  bind   nofail,defaults,bind 0 0" >> /etc/fstab
# TODO use systemctl instead of pg_ctlcluster on CentOS
pg_ctlcluster 9.5 main start

# Disable /mnt line for /dev/xvdb
umount /mnt
sed -i 's|^/dev/xvdb|#/dev/xvdb|' /etc/fstab
