# Dockerfile for a generic Ubuntu image with just the basics we need
# to make it suitable for CI.  In particular:
#  * a non-root user to run as (a pain to try to do in setup,
#    because by then we've already cloned the repo);
#  * Git and other basic utilities.

# To rebuild from this file for a given release, say Ubuntu 18.04 bionic:
#   docker build . --build-arg=BASE_IMAGE=ubuntu:18.04 --pull --tag=zulip/ci:bionic
#   docker push zulip/ci:bionic
#
# tools/ci/build-docker-images will rebuild all images, but not push them.

ARG BASE_IMAGE
FROM $BASE_IMAGE

RUN ln -sf /usr/share/zoneinfo/Etc/UTC /etc/localtime

# Set the locale.
ENV LC_ALL C.UTF-8

# Upgrade git if it is less than v2.18 because GitHub Actions'
# checkout installs source code using Rest API as an optimization
# if the version is less than v2.18, which causes failure in provision
# and tests because of the lack of git being initialized.
RUN if (. /etc/os-release && [ "$ID $VERSION_ID" = 'ubuntu 18.04' ]); then \
      apt-get update && \
      apt-get -y install software-properties-common && \
      add-apt-repository -y ppa:git-core/ppa; \
    fi

# Extra packages used by Zulip.
RUN apt-get update \
  && apt-get -y install --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    gettext \
    git \
    hunspell-en-us \
    jq \
    libffi-dev \
    libfreetype6-dev \
    libjpeg-dev \
    libldap2-dev \
    libpq-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    locales \
    memcached \
    moreutils \
    puppet \
    python3-dev \
    python3-pip \
    rabbitmq-server \
    redis-server \
    sudo \
    supervisor \
    unzip \
    xvfb \
    zlib1g-dev

ARG USERNAME=github
RUN groupadd --gid 1001 $USERNAME \
  && useradd --uid 1001 --gid $USERNAME --shell /bin/bash --create-home $USERNAME \
  && echo "$USERNAME ALL = (ALL) NOPASSWD: ALL" >> /etc/sudoers.d/50-$USERNAME \
  && echo 'Defaults    env_keep += "DEBIAN_FRONTEND"' >> /etc/sudoers.d/env_keep

USER $USERNAME

CMD ["/bin/sh"]
