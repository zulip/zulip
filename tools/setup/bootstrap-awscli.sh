# shellcheck shell=bash

set -eu

ARCH=$(uname -m)

AWS_CLI_VERSION="2.8.1"
if [ "$ARCH" == "x86_64" ]; then
    AWS_CLI_SHA="8253e0567ff15d8cc3dc24d9dcbc41753a59662a006849e3b584a73a48f23b0d"
elif [ "$ARCH" == "aarch64" ]; then
    AWS_CLI_SHA="56f22efb25c8b5648d9616e4b89b5a0c12b13037520b870017dce5622ff10e77"
else
    echo "Unsupported architecture: $ARCH"
    exit 1
fi

if [ ! -d "/srv/zulip-aws-tools/v2/$AWS_CLI_VERSION" ]; then
    mkdir -p /srv/zulip-aws-tools
    (
        cd /srv/zulip-aws-tools || exit 1
        rm -rf awscli.zip awscli.zip.sha256 aws/
        curl -fL --retry 3 "https://awscli.amazonaws.com/awscli-exe-linux-$ARCH-$AWS_CLI_VERSION.zip" -o awscli.zip
        echo "$AWS_CLI_SHA  awscli.zip" >awscli.zip.sha256
        sha256sum -c awscli.zip.sha256
        unzip -q awscli.zip

        cd ./aws || exit 1
        ./install -i /srv/zulip-aws-tools -b /srv/zulip-aws-tools/bin -u
    )
    rm -rf awscli.zip awscli.zip.sha256 aws/
fi

# shellcheck disable=SC2034
AWS="/srv/zulip-aws-tools/bin/aws"
