FROM ubuntu:22.04

ARG UBUNTU_MIRROR

# Basic packages and dependencies of docker-systemctl-replacement
RUN echo locales locales/default_environment_locale select C.UTF-8 | debconf-set-selections \
    && echo locales locales/locales_to_be_generated select "C.UTF-8 UTF-8" | debconf-set-selections \
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
           openssh-server \
           python3 \
           sudo \
           systemd \
    && rm -rf /var/lib/apt/lists/*

ARG VAGRANT_UID

RUN \
    # We use https://github.com/gdraheim/docker-systemctl-replacement
    # to make services we install like PostgreSQL, Redis, etc. normally
    # managed by systemd start within Docker, which breaks normal
    # operation of systemd.
    dpkg-divert --add --rename /bin/systemctl \
    && curl -fLsS --retry 3 -o /bin/systemctl 'https://raw.githubusercontent.com/gdraheim/docker-systemctl-replacement/v1.5.8066/files/docker/systemctl3.py' \
    && echo 'f8736b56299374a316a958e5e949be73e657e2f7069691381664d94950c645c9  /bin/systemctl' | sha256sum -c \
    && chmod +x /bin/systemctl \
    && ln -nsf /bin/true /usr/sbin/policy-rc.d \
    && mkdir -p /run/sshd \
    # docker-systemctl-replacement doesn’t work with template units yet:
    # https://github.com/gdraheim/docker-systemctl-replacement/issues/62
    && ln -ns /lib/systemd/system/postgresql@.service /etc/systemd/system/multi-user.target.wants/postgresql@14-main.service \
    # Set up the vagrant user and its SSH key (globally public)
    && useradd -ms /bin/bash -u "$VAGRANT_UID" vagrant \
    && mkdir -m 700 ~vagrant/.ssh \
    && curl -fLsS --retry 3 -o ~vagrant/.ssh/authorized_keys 'https://raw.githubusercontent.com/hashicorp/vagrant/be7876d83644aa6bdf7f951592fdc681506bcbe6/keys/vagrant.pub' \
    && chown -R vagrant: ~vagrant/.ssh \
    && echo 'vagrant ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/vagrant

CMD ["/bin/systemctl"]

EXPOSE 22
EXPOSE 9991
