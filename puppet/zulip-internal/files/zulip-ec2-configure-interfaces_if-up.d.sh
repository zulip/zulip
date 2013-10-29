#! /bin/sh
# Run zulip-ec2-configure-interfaces when eth0 is brought up

set -e

# Only run from ifup.
if [ "$MODE" != start ]; then
	exit 0
fi

if [ "$IFACE" = eth0 ]; then
	/usr/local/sbin/zulip-ec2-configure-interfaces
fi
