FROM quay.io/sameersbn/ubuntu:14.04.20170608
MAINTAINER Alexander Trost <galexrt@googlemail.com>

ENV ZULIP_VERSION="1.7.0" DATA_DIR="/data"

RUN apt-get -q update && \
    apt-get -q dist-upgrade -y && \
    mkdir -p "$DATA_DIR" /root/zulip && \
    wget -q "https://www.zulip.org/dist/releases/zulip-server-$ZULIP_VERSION.tar.gz" -O /tmp/zulip-server.tar.gz && \
    tar xfz /tmp/zulip-server.tar.gz -C /root/zulip --strip-components=1 && \
    rm -rf /tmp/zulip-server.tar.gz && \
    export PUPPET_CLASSES="zulip::dockervoyager" DEPLOYMENT_TYPE="dockervoyager" \
        ADDITIONAL_PACKAGES="python-dev python-six" has_nginx="0" has_appserver="0" && \
    /root/zulip/scripts/setup/install && \
    apt-get -qq autoremove --purge -y && \
    apt-get -qq clean && \
    rm -rf /root/zulip/puppet/ /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY docker-entrypoint.sh /sbin/entrypoint.sh
COPY scripts/lib/docker-functions.sh /opt/docker-functions.sh

VOLUME ["$DATA_DIR"]
EXPOSE 80 443

ENTRYPOINT ["/sbin/entrypoint.sh"]
CMD ["app:run"]
