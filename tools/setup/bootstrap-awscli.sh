# shellcheck shell=bash

set -eu

ARCH=$(uname -m)

AWS_CLI_VERSION="2.4.7"
if [ "$ARCH" == "x86_64" ]; then
    AWS_CLI_SHA="925810ba09815ef53997b901c76bd448c3caa593b5da1ccad79d17946ec94ab4"
elif [ "$ARCH" == "aarch64" ]; then
    AWS_CLI_SHA="fa01abcef75f910661d19fdf78615f9be66f9e8f1c9bd7980324bb10291a887e"
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
