#!/bin/sh
umount /mnt
yes | mdadm --create /dev/md0 --raid-devices=2 --level=1 /dev/xvdb /dev/xvdc

blockdev --setra 4096 /dev/xvdb
blockdev --setra 4096 /dev/xvdc
blockdev --setra 4096 /dev/md0
echo deadline > /sys/block/xvdb/queue/scheduler
echo deadline > /sys/block/xvdc/queue/scheduler

mkfs.xfs /dev/md0
echo "/dev/md0   /srv  xfs    noatime,barrier 1 1" >> /etc/fstab
mount /srv

pg_ctlcluster 9.1 main stop
mv /var/lib/postgresql /srv
ln -s /srv/postgresql/ /var/lib

mv /tmp /srv
mkdir /tmp
mount --bind /srv/tmp /tmp
echo "/srv/tmp   /tmp  bind   defaults,bind 0 0" >> /etc/fstab
pg_ctlcluster 9.1 main start
