# shellcheck shell=bash

ARCH=$(uname -m)

AWS_CLI_VERSION="2.0.30"
if [ "$ARCH" == "x86_64" ]; then
    AWS_CLI_SHA="7ee475f22c1b35cc9e53affbf96a9ffce91706e154a9441d0d39cbf8366b718e"
elif [ "$ARCH" == "aarch64" ]; then
    AWS_CLI_SHA="624ebb04705d4909eb0d56d467fe6b8b5c53a8c59375ed520e70236120125077"
else
    echo "Unsupported architecture: $ARCH"
    exit 1
fi

if [ ! -d "/srv/zulip-aws-tools/v2/$AWS_CLI_VERSION" ]; then
    mkdir -p /srv/zulip-aws-tools
    cd /srv/zulip-aws-tools || exit 1
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
