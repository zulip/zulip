FROM ubuntu:18.04

ARG UBUNTU_MIRROR

# Basic packages and things we need to get Vagrant to connect to us
RUN echo locales locales/default_environment_locale select en_US.UTF-8 | debconf-set-selections \
    && echo locales locales/locales_to_be_generated select "en_US.UTF-8 UTF-8" | debconf-set-selections \
    && { [ ! "$UBUNTU_MIRROR" ] || sed -i "s|http://\(\w*\.\)*archive\.ubuntu\.com/ubuntu/\? |$UBUNTU_MIRROR |" /etc/apt/sources.list; } \
    # This restores man pages and other documentation that have been
    # stripped from the default Ubuntu cloud image and installs
    # ubuntu-minimal and ubuntu-standard.
    #
    # This makes sense to do because we're using this image as a
    # development environment, not a minimal production system.
    && printf 'y\n\n' | unminimize \
    && apt-get install --no-install-recommends -y \
           ca-certificates \
           curl \
           locales \
           lsb-release \
           openssh-server \
           # python3 is redundant but left for now to avoid invalidating a Docker layer.
           python3 \
           sudo \
           systemd \
    && rm -rf /var/lib/apt/lists/*

ARG VAGRANT_UID

RUN \
    ln -nsf /bin/true /usr/sbin/policy-rc.d \
    # redis fails to start with the default configuration if IPv6 is disabled:
    # https://github.com/antirez/redis/pull/5598
    && mkdir /etc/systemd/system/redis-server.service.d \
    && printf '[Service]\nExecStart=\nExecStart=/usr/bin/redis-server /etc/redis/redis.conf --bind 127.0.0.1\n' > /etc/systemd/system/redis-server.service.d/override.conf \
    # Set up the vagrant user and its SSH key (globally public)
    && useradd -ms /bin/bash -u "$VAGRANT_UID" vagrant \
    && mkdir -m 700 ~vagrant/.ssh \
    && curl -so ~vagrant/.ssh/authorized_keys 'https://raw.githubusercontent.com/hashicorp/vagrant/be7876d83644aa6bdf7f951592fdc681506bcbe6/keys/vagrant.pub' \
    && chown -R vagrant: ~vagrant/.ssh \
    && echo 'vagrant ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/vagrant

CMD ["/lib/systemd/systemd"]

EXPOSE 22
EXPOSE 9991
