# shellcheck shell=bash

set -eu

ARCH=$(uname -m)

AWS_CLI_VERSION="2.4.26"
if [ "$ARCH" == "x86_64" ]; then
    AWS_CLI_SHA="20d0f048b32782c67fcb1495928deec5aa4e4e93cb67778a0f5a4f14de0c4b8d"
elif [ "$ARCH" == "aarch64" ]; then
    AWS_CLI_SHA="c7e5b9a4893aa51a51af7ff95db0a41d695f90509b13787935d6ff9a5b60e2a5"
else
    echo "Unsupported architecture: $ARCH"
    exit 1
fi

if [ ! -d "/srv/zulip-aws-tools/v2/$AWS_CLI_VERSION" ]; then
    mkdir -p /srv/zulip-aws-tools
    cd /srv/zulip-aws-tools
    rm -rf awscli.zip awscli.zip.sha256 aws/
    curl -fL "https://awscli.amazonaws.com/awscli-exe-linux-$ARCH-$AWS_CLI_VERSION.zip" -o awscli.zip
    echo "$AWS_CLI_SHA  awscli.zip" >awscli.zip.sha256
    sha256sum -c awscli.zip.sha256
    unzip -q awscli.zip
    (
        cd ./aws || exit 1
        ./install -i /srv/zulip-aws-tools -b /srv/zulip-aws-tools/bin -u
    )
    rm -rf awscli.zip awscli.zip.sha256 aws/
fi

# shellcheck disable=SC2034
AWS="/srv/zulip-aws-tools/bin/aws"
