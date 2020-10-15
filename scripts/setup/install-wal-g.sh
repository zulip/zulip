#!/bin/sh

set -e
set -x

VERSION="$1"
HASH="$2"

cd /tmp
wget -qO "wal-g-$VERSION.tar.gz" \
    "https://github.com/wal-g/wal-g/releases/download/v$VERSION/wal-g.linux-amd64.tar.gz"

# Check not against the arbitrary provided sha256 on Github, but
# against the (same) sha256 that we hardcode as "known good".
echo "$HASH  wal-g-$VERSION.tar.gz" >"wal-g-$VERSION.tar.gz.sha256"
sha256sum -c "wal-g-$VERSION.tar.gz.sha256"

tar xzf "wal-g-$VERSION.tar.gz"
mv wal-g "/usr/local/bin/wal-g-$VERSION"
rm "wal-g-$VERSION.tar.gz" "wal-g-$VERSION.tar.gz.sha256"
