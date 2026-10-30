# syntax=docker/dockerfile:1
# Build and run the enrolled zulip/zulip checkout with a local, offline test stack.
# /src: audit source; /root/zulip: release tree; /opt/docker-zulip: test harness.
FROM ubuntu:24.04 AS base

ENV LANG="C.UTF-8"

RUN apt-get -q update && \
    apt-get -q dist-upgrade -y && \
    DEBIAN_FRONTEND=noninteractive \
    apt-get -q install --no-install-recommends -y ca-certificates git locales python3 sudo tzdata && \
    touch /var/mail/ubuntu && chown ubuntu /var/mail/ubuntu && userdel -r ubuntu && \
    useradd -d /home/zulip -m zulip -u 1000

FROM base AS build

RUN echo 'zulip ALL=(ALL:ALL) NOPASSWD:ALL' >> /etc/sudoers

USER zulip
WORKDIR /home/zulip

# Build the enrolled checkout, rather than cloning a separately pinned release.
COPY --chown=zulip:zulip . /home/zulip/zulip
WORKDIR /home/zulip/zulip
RUN SKIP_VENV_SHELL_WARNING=1 ./tools/provision --build-release-tarball-only && \
    uv run --no-sync ./tools/build-release-tarball docker && \
    mv /tmp/tmp.*/zulip-server-docker.tar.gz /tmp/zulip-server-docker.tar.gz


FROM base

ENV DATA_DIR="/data" \
    SETTING_EXTERNAL_HOST="zulip.example.net" \
    SETTING_ZULIP_ADMINISTRATOR="admin@example.net"

COPY --from=build /tmp/zulip-server-docker.tar.gz /root/
# Docker packaging is build/test infrastructure, not the scan target.
ARG DOCKER_ZULIP_REF=916aeb2348c9648ad2271225f54560ae4c31b655
RUN git clone https://github.com/zulip/docker-zulip.git /opt/docker-zulip && \
    git -C /opt/docker-zulip checkout "$DOCKER_ZULIP_REF" && \
    cp -a /opt/docker-zulip/custom_zulip_files /root/custom_zulip

WORKDIR /root
# As the production Dockerfile does, but with the PostgreSQL, memcached, RabbitMQ and Redis puppet profiles added, and
# without deleting /etc/zulip/zulip-secrets.conf: the local services were configured with the passwords in it, and
# entrypoint.sh keeps whatever secrets it finds there.
RUN \
    dpkg-divert --add --rename /etc/init.d/nginx && \
    ln -s /bin/true /etc/init.d/nginx && \
    mkdir -p "$DATA_DIR" && \
    tar -xf zulip-server-docker.tar.gz && \
    rm -f zulip-server-docker.tar.gz && \
    mv zulip-server-docker zulip && \
    cp -rf /root/custom_zulip/* /root/zulip && \
    rm -rf /root/custom_zulip && \
    /root/zulip/scripts/setup/install --hostname="docker-zulip.local" --email="docker-zulip" \
      --puppet-classes="zulip::profile::docker,zulip::profile::postgresql,zulip::profile::memcached,zulip::profile::rabbitmq,zulip::profile::redis" \
      --postgresql-version=14 && \
    rm -f /etc/zulip/settings.py && \
    touch /.dockerenv && \
    apt-get -qq autoremove --purge -y && \
    apt-get -qq clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN apt-get -q update && \
    DEBIAN_FRONTEND=noninteractive apt-get -q install --no-install-recommends -y jq curl procps && \
    rm -rf /var/lib/apt/lists/*
RUN install -m 755 /opt/docker-zulip/entrypoint.sh /sbin/entrypoint.sh && \
    install -m 755 /opt/docker-zulip/zulip-certbot-setup /usr/local/sbin/zulip-certbot-setup

COPY --chmod=755 <<'SCANNER_SCRIPT' /usr/local/bin/zulip-start
#!/bin/bash
# Start the local services, then the real entrypoint (which migrates, configures and runs supervisord) in the background.
set -e
if [ -w /etc/hosts ] && ! grep -q zulip.example.net /etc/hosts; then
    echo "127.0.0.1 zulip.example.net" >> /etc/hosts
fi
for s in postgresql memcached redis-server rabbitmq-server; do service "$s" start; done
if ! pgrep -f "supervisord -n" >/dev/null; then
    (nohup /sbin/entrypoint.sh app:run >/var/log/zulip-entrypoint.log 2>&1 &)
fi
for _ in $(seq 1 600); do
    curl -sf -H "Host: zulip.example.net" http://127.0.0.1/health >/dev/null 2>&1 && exit 0
    sleep 1
done
echo "Zulip did not become healthy; see /var/log/zulip-entrypoint.log" >&2
exit 1
SCANNER_SCRIPT

COPY --chmod=755 <<'SCANNER_SCRIPT' /usr/local/bin/zulip-stop
#!/bin/bash
pkill -f "supervisord -n" 2>/dev/null
supervisorctl shutdown 2>/dev/null
for s in rabbitmq-server redis-server memcached postgresql; do service "$s" stop; done
true
SCANNER_SCRIPT

COPY --chmod=755 <<'SCANNER_SCRIPT' /usr/local/bin/zulip-setup
#!/bin/bash
# Build-time setup: create the database, run the entrypoint once (settings and migrations), and create a realm.
set -ex
if [ -w /etc/hosts ] && ! grep -q zulip.example.net /etc/hosts; then
    echo "127.0.0.1 zulip.example.net" >> /etc/hosts
fi
for s in postgresql memcached redis-server rabbitmq-server; do service "$s" start; done

# What scripts/setup/create-database does, without its stop-server step (there is no server yet). Zulip reaches the
# database over TCP with the password from zulip-secrets.conf, as it does against the zulip-postgresql container.
(cd / && su postgres -c "psql -v ON_ERROR_STOP=1 -v dbname=zulip -v dbuser=zulip -e") \
    < /root/zulip/scripts/setup/create-db.sql
# Compose supplies this secret from outside; here it is a fixed, local-only password.
password=oss-scanner-local-postgres-password
crudini --set /etc/zulip/zulip-secrets.conf secrets postgres_password "$password"
(cd / && su postgres -c "psql -v ON_ERROR_STOP=1 -e postgres") <<SQL
ALTER ROLE zulip PASSWORD '$password';
SQL

/sbin/entrypoint.sh app:init

manage=/home/zulip/deployments/current/manage.py
su zulip -c "$manage create_realm 'Testing Realm' admin@example.com 'Test Admin' --password very-secret"
su zulip -c "$manage create_user --realm '' --password very-secret user@example.com 'Test User'"

/usr/local/bin/zulip-stop
SCANNER_SCRIPT

# Run the entrypoint once so the database is migrated and the settings are written, then create a realm with an
# administrator and a regular user.
RUN zulip-setup

VOLUME ["$DATA_DIR"]
EXPOSE 25 80 443

# Keep the full enrolled source tree available for auditing and patching.
COPY . /src
WORKDIR /src

# A working application is required for the offline audit.
RUN if zulip-start && \
       curl -sf --noproxy "*" --resolve zulip.example.net:80:127.0.0.1 http://zulip.example.net/ -o /dev/null -L; then \
        zulip-stop; \
    else \
        cat /var/log/zulip-entrypoint.log; zulip-stop; exit 1; \
    fi
