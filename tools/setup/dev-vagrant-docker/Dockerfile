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
    curl -fLsS --retry 3 --output-dir /bin -O 'https://raw.githubusercontent.com/gdraheim/docker-systemctl-replacement/v1.7.1097/files/docker/systemctl3.py' -O 'https://raw.githubusercontent.com/gdraheim/docker-systemctl-replacement/v1.7.1097/files/docker/journalctl3.py' \
    && printf '5f5a47f321c7a8881dfd01f774106dc4012d664bee238eada86a7112674fea93  /bin/systemctl3.py\n16a52fe484d7c0fca464c82a56de58980440362942482c0d1fbc424e69f8f833  /bin/journalctl3.py\n' | sha256sum -c \
    && chmod +x /bin/systemctl3.py /bin/journalctl3.py \
    && dpkg-divert --add --rename /bin/systemctl \
    && ln -s systemctl3.py /bin/systemctl \
    && dpkg-divert --add --rename /bin/journalctl \
    && ln -s journalctl3.py /bin/journalctl \
    && ln -nsf /bin/true /usr/sbin/policy-rc.d \
    && mkdir -p /run/sshd \
    # docker-systemctl-replacement doesn’t work with template units yet:
    # https://github.com/gdraheim/docker-systemctl-replacement/issues/62
    && ln -ns /lib/systemd/system/postgresql@.service /etc/systemd/system/multi-user.target.wants/postgresql@14-main.service \
    # Set up the vagrant user and its SSH key (globally public)
    && useradd -ms /bin/bash -u "$VAGRANT_UID" vagrant \
    && mkdir -m 700 ~vagrant/.ssh \
    && curl -fLsS --retry 3 -o ~vagrant/.ssh/authorized_keys 'https://raw.githubusercontent.com/hashicorp/vagrant/v2.4.0/keys/vagrant.pub' \
    && echo '55009a554ba2d409565018498f1ad5946854bf90fa8d13fd3fdc2faa102c1122  /home/vagrant/.ssh/authorized_keys' | sha256sum -c \
    && chown -R vagrant: ~vagrant/.ssh \
    && echo 'vagrant ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/vagrant

CMD ["/bin/systemctl"]

EXPOSE 22
EXPOSE 9991
