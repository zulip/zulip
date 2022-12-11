# shellcheck shell=bash

set -eu

ARCH=$(uname -m)

AWS_CLI_VERSION="2.8.9"
if [ "$ARCH" == "x86_64" ]; then
    AWS_CLI_SHA="66ce7e305a8fa4e8a140ed30766e6d67a39e299ad2413fdf347da176890597d9"
elif [ "$ARCH" == "aarch64" ]; then
    AWS_CLI_SHA="5329130a487993a794bbc12d91b3f463cab484a35ff2faf6ddc355a3d3e82c24"
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
