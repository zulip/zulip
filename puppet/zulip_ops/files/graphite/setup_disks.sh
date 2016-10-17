#!/bin/sh

mkdir /srv/graphite
mkfs.ext4 /dev/xvdb

echo "/dev/xvdb   /srv/graphite  ext4    noatime,defaults,barrier=0 1 1" >> /etc/fstab
mount /srv/graphite

mkfs.ext4 /dev/xvdf1
echo "/dev/xvdf1   /mnt/graphite-backup  ext4    noatime,defaults,barrier=0 1 1" >> /etc/fstab
mount /mnt/graphite-backup
