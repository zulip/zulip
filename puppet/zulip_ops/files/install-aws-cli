# shellcheck shell=bash

set -eu

ARCH=$(uname -m)

AWS_CLI_VERSION="2.13.15"
if [ "$ARCH" == "x86_64" ]; then
    AWS_CLI_SHA="45d2e0f304eb0f57e6b58ffc0664879c0bc1cf8365fd2f64bcb5f3bbf2e9434f"
elif [ "$ARCH" == "aarch64" ]; then
    AWS_CLI_SHA="74ae95fcc50f7a96cf9479969343fc8a95ff06da23403162cc9249fae79f3bfc"
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
