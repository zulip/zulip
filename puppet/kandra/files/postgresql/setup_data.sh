#!/usr/bin/env bash

set -eux

service postgresql stop

cert_file="$(crudini --get /etc/zulip/zulip.conf postgresql ssl_cert_file)"
if [ -z "$cert_file" ] || [ ! -f "$cert_file" ]; then
    echo "Certificate file is not set or does not exist!"
    exit 1
fi

key_file="$(crudini --get /etc/zulip/zulip.conf postgresql ssl_key_file)"
if [ -z "$key_file" ] || [ ! -f "$key_file" ]; then
    echo "Key file is not set or does not exist!"
    exit 1
fi

cert_cn="$(openssl x509 -noout -subject -in "$cert_file" | sed -n '/^subject/s/^.*CN\s*=\s*//p')"

if [ "$cert_cn" != "$(hostname)" ]; then
    echo "Configured certificate does not match host!"
    exit 1
fi

echo "Checking for S3 secrets..."
crudini --get /etc/zulip/zulip-secrets.conf secrets s3_region >/dev/null
crudini --get /etc/zulip/zulip-secrets.conf secrets s3_backups_bucket >/dev/null
crudini --get /etc/zulip/zulip-secrets.conf secrets s3_backups_key >/dev/null
crudini --get /etc/zulip/zulip-secrets.conf secrets s3_backups_secret_key >/dev/null

if [ ! -f "/var/lib/postgresql/.postgresql/postgresql.crt" ]; then
    echo "Replication certificate file is not set or does not exist!"
    exit 1
fi
if [ ! -f "/var/lib/postgresql/.postgresql/postgresql.key" ]; then
    echo "Replication key file is not set or does not exist!"
    exit 1
fi

version="$(crudini --get /etc/zulip/zulip.conf postgresql version)"
mkdir -p "/srv/data/postgresql/$version"
chown postgres.postgres "/srv/data/postgresql/$version"
chmod 700 "/srv/data/postgresql/$version"

/usr/local/bin/env-wal-g backup-fetch "/var/lib/postgresql/$version/main" LATEST
chown -R postgres.postgres "/var/lib/postgresql/$version/main"
