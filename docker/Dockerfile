# ============================================================
# Base común
# ============================================================
FROM ubuntu:24.04 AS base

ENV LANG="C.UTF-8"

ARG UBUNTU_MIRROR

# hadolint ignore=DL3005,DL3008,DL3009
RUN apt-get -q update && \
    apt-get -q dist-upgrade -y && \
    DEBIAN_FRONTEND=noninteractive \
    apt-get -q install --no-install-recommends -y \
        ca-certificates \
        git \
        locales \
        python3 \
        sudo \
        tzdata && \
    touch /var/mail/ubuntu && \
    chown ubuntu /var/mail/ubuntu && \
    userdel -r ubuntu && \
    useradd -d /home/zulip -m zulip -u 1000


# ============================================================
# Stage 1: construcción
# ============================================================
FROM base AS build

RUN echo 'zulip ALL=(ALL:ALL) NOPASSWD:ALL' >> /etc/sudoers

USER zulip
WORKDIR /home/zulip

ARG ZULIP_GIT_URL=https://github.com/facaslo/zulip-server-unal.git
ARG ZULIP_GIT_REF=12.3

LABEL org.opencontainers.image.source="https://github.com/facaslo/zulip-server-unal"
LABEL org.opencontainers.image.licenses="Apache-2.0"
LABEL org.opencontainers.image.title="Zulip Server UNAL"
LABEL org.opencontainers.image.version="${ZULIP_GIT_REF}"

RUN git clone "$ZULIP_GIT_URL" zulip

WORKDIR /home/zulip/zulip

RUN git checkout "$ZULIP_GIT_REF"

RUN SKIP_VENV_SHELL_WARNING=1 ./tools/provision --build-release-tarball-only && \
    uv run --no-sync ./tools/build-release-tarball docker && \
    mv /tmp/tmp.*/zulip-server-docker.tar.gz \
       /tmp/zulip-server-docker.tar.gz


# ============================================================
# Stage 2: runtime
# ============================================================
FROM base AS runtime

ENV DATA_DIR="/data"

COPY --from=build /tmp/zulip-server-docker.tar.gz /root/

WORKDIR /root

RUN dpkg-divert --add --rename /etc/init.d/nginx && \
    ln -s /bin/true /etc/init.d/nginx && \
    mkdir -p "$DATA_DIR" && \
    tar -xf zulip-server-docker.tar.gz && \
    rm -f zulip-server-docker.tar.gz && \
    mv zulip-server-docker zulip && \
    /root/zulip/scripts/setup/install \
        --hostname="docker-zulip.local" \
        --email="docker-zulip" \
        --puppet-classes="zulip::profile::docker" \
        --postgresql-version=14 && \
    rm -f /etc/zulip/zulip-secrets.conf \
          /etc/zulip/settings.py && \
    touch /.dockerenv && \
    apt-get -qq autoremove --purge -y && \
    apt-get -qq clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY entrypoint.sh /sbin/entrypoint.sh
COPY zulip-certbot-setup /usr/local/sbin/zulip-certbot-setup

VOLUME ["${DATA_DIR}"]

EXPOSE 25 80 443

HEALTHCHECK \
    --interval=10s \
    --timeout=5s \
    --retries=3 \
    --start-period=300s \
    CMD ["curl", "-isfL", "--insecure", "http://localhost/health"]

ENTRYPOINT ["/sbin/entrypoint.sh"]

CMD ["app:run"]