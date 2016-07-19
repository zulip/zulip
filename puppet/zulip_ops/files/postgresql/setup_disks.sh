#!/bin/sh
umount /mnt
yes | mdadm --create /dev/md0 --raid-devices=2 --level=1 /dev/xvdb /dev/xvdc
# Add disk to mdadm.conf so it will be enabled on boot
mdadm --examine --scan | sed 's/  metadata=1.2//; s/ name.*//; s|md/0|md0|' >> /etc/mdadm/mdadm.conf

blockdev --setra 4096 /dev/xvdb
blockdev --setra 4096 /dev/xvdc
blockdev --setra 4096 /dev/md0
echo deadline > /sys/block/xvdb/queue/scheduler
echo deadline > /sys/block/xvdc/queue/scheduler

mkfs.xfs /dev/md0

array_name=$(mdadm --examine --scan | sed 's/.*name=//')
echo "/dev/md0   /srv  xfs    nofail,noatime,barrier 1 1" >> /etc/fstab
mount /srv

pg_ctlcluster 9.5 main stop
mv /var/lib/postgresql /srv
ln -s /srv/postgresql/ /var/lib

mv /tmp /srv
mkdir /tmp
mount --bind /srv/tmp /tmp
echo "/srv/tmp   /tmp  bind   nofail,defaults,bind 0 0" >> /etc/fstab
pg_ctlcluster 9.5 main start

# Disable /mnt line for /dev/xvdb
umount /mnt
sed -i 's|^/dev/xvdb|#/dev/xvdb|' /etc/fstab

# Update the initrd so we can use the new array post-boot
update-initramfs -u
