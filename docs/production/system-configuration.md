## System configuration

The file `/etc/zulip/zulip.conf` is an [INI
format](https://en.wikipedia.org/wiki/INI_file) configuration file
used to configure properties of the system and deployment;
`/etc/zulip/settings.py` is used to [configure the application
itself](settings.md). The `zulip.conf` sections and settings are
described below. Changes to `zulip.conf` generally do not take effect
until you run `zulip-puppet-apply` as root:

```console
# /home/zulip/deployments/current/scripts/zulip-puppet-apply
```

The `zulip-puppet-apply` command will display the configuration
changes it will make and prompt for you to confirm you'd like to make
those changes, before executing them (if you approve).

### Truthy values

When a setting refers to "set to true" or "set to false", the values
`true` and `false` are canonical, but any of the following values will
be considered "true", case-insensitively:

- 1
- y
- t
- yes
- true
- enable
- enabled

Any other value (including the empty string) is considered false.

### `[machine]`

#### `puppet_classes`

A comma-separated list of the Puppet classes to install on the server.
The most common is **`zulip::profile::standalone`**, used for a
stand-alone single-host deployment.
[Components](../overview/architecture-overview.md#components) of
that include:

- **`zulip::profile::app_frontend`**
- **`zulip::profile::memcached`**
- **`zulip::profile::postgresql`**
- **`zulip::profile::rabbitmq`**
- **`zulip::profile::redis`**
- **`zulip::profile::smokescreen`**

If you are using a [Apache as a single-sign-on
authenticator](authentication-methods.md#apache-based-sso-with-remote_user),
you will need to add **`zulip::apache_sso`** to the list.

#### `pgroonga`

Set to true if enabling the [multi-language PGroonga search
extension](../subsystems/full-text-search.md#multi-language-full-text-search).

#### `timesync`

What time synchronization daemon to use; defaults to `chrony`, but also supports
`ntpd` and `none`. Installations should not adjust this unless they are aligning
with a fleet-wide standard of `ntpd`. `none` is only reasonable in containers
like LXC which do not allow adjustment of the clock; a Zulip server will not
function correctly without an accurate clock.

### `[deployment]`

#### `deploy_options`

Options passed by `upgrade-zulip` and `upgrade-zulip-from-git` into
`upgrade-zulip-stage-2`. These might be any of:

- **`--skip-puppet`** skips doing Puppet/apt upgrades. The user will need
  to run `zulip-puppet-apply` manually after the upgrade.
- **`--skip-migrations`** skips running database migrations. The
  user will need to run `./manage.py migrate` manually after the upgrade.
- **`--skip-purge-old-deployments`** skips purging old deployments;
  without it, only deployments with the last two weeks are kept.

Generally installations will not want to set any of these options; the
`--skip-*` options are primarily useful for reducing upgrade downtime
for servers that are upgraded frequently by core Zulip developers.

#### `git_repo_url`

Default repository URL used when [upgrading from a Git
repository](upgrade.md#upgrading-from-a-git-repository).

### `[application_server]`

#### `http_only`

If set to true, [configures Zulip to allow HTTP access][using-http];
use if Zulip is deployed behind a reverse proxy that is handling
SSL/TLS termination.

#### `nginx_listen_port`

Set to the port number if you [prefer to listen on a port other than
443](deployment.md#using-an-alternate-port).

#### `nginx_worker_connections`

Adjust the [`worker_connections`][nginx_worker_connections] setting in
the nginx server. This defaults to 10000; increasing it allows more
concurrent connections per CPU core, at the cost of more memory
consumed by NGINX. This number, times the number of CPU cores, should
be more than twice the concurrent number of users.

[nginx_worker_connections]: http://nginx.org/en/docs/ngx_core_module.html#worker_connections

#### `queue_workers_multiprocess`

By default, Zulip automatically detects whether the system has enough
memory to run Zulip queue processors in the higher-throughput but more
multiprocess mode (or to save 1.5GiB of RAM with the multithreaded
mode). The calculation is based on whether the system has enough
memory (currently 3.5GiB) to run a single-server Zulip installation in
the multiprocess mode.

Set explicitly to true or false to override the automatic
calculation. This override is useful both Docker systems (where the
above algorithm might see the host's memory, not the container's)
and/or when using remote servers for postgres, memcached, redis, and
RabbitMQ.

#### `rolling_restart`

If set to true, when using `./scripts/restart-server` to restart
Zulip, restart the uwsgi processes one-at-a-time, instead of all at
once. This decreases the number of 502's served to clients, at the
cost of slightly increased memory usage, and the possibility that
different requests will be served by different versions of the code.

#### `service_file_descriptor_limit`

The number of file descriptors which [Supervisor is configured to allow
processes to use][supervisor-minfds]; defaults to 40000. If your Zulip deployment
is very large (hundreds of thousands of concurrent users), your Django processes
hit this limit and refuse connections to clients. Raising it above this default
may require changing system-level limits, particularly if you are using a
virtualized environment (e.g. Docker, or Proxmox LXC).

[supervisor-minfds]: http://supervisord.org/configuration.html?highlight=minfds#supervisord-section-values

#### `s3_memory_cache_size`

Used only when the [S3 storage backend][s3-backend] is in use.
Controls the in-memory size of the cache _index_; the default is 1MB,
which is enough to store about 8 thousand entries.

#### `s3_disk_cache_size`

Used only when the [S3 storage backend][s3-backend] is in use.
Controls the on-disk size of the cache _contents_; the default is
200MB.

#### `s3_cache_inactive_time`

Used only when the [S3 storage backend][s3-backend] is in use.
Controls the longest amount of time an entry will be cached since last
use; the default is 30 days. Since the contents of the cache are
immutable, this serves only as a potential additional limit on the
size of the contents on disk; `s3_disk_cache_size` is expected to be
the primary control for cache sizing.

#### `nameserver`

When the [S3 storage backend][s3-backend] is in use, downloads from S3 are
proxied from nginx, whose configuration requires an explicit value of a DNS
nameserver to resolve the S3 server's hostname. Zulip defaults to using the
resolver found in `/etc/resolv.conf`; this setting overrides any value found
there.

[s3-backend]: upload-backends.md

#### `uwsgi_listen_backlog_limit`

Override the default uwsgi backlog of 128 connections.

#### `uwsgi_processes`

Override the default `uwsgi` (Django) process count of 6 on hosts with
more than 3.5GiB of RAM, 4 on hosts with less.

#### `access_log_retention_days`

Number of days of access logs to keep, for both nginx and the application.
Defaults to 14 days.

#### `katex_server`

Set to a true value to run a separate service for [rendering math with
LaTeX](https://zulip.com/help/latex). This is not necessary except on servers
with users who send several math blocks in a single message; it will address
issues with such messages occasionally failing to send, at cost of a small
amount of increased memory usage.

#### `katex_server_port`

Set to the port number for the KaTeX server, if enabled; defaults to port 9700.

### `[postfix]`

#### `mailname`

The hostname that [Postfix should be configured to receive mail
at](email-gateway.md#local-delivery-setup), as well as identify itself as for
outgoing email.

### `[postgresql]`

#### `effective_io_concurrency`

Override PostgreSQL's [`effective_io_concurrency`
setting](https://www.postgresql.org/docs/current/runtime-config-resource.html#GUC-EFFECTIVE-IO-CONCURRENCY).

#### `listen_addresses`

Override PostgreSQL's [`listen_addresses`
setting](https://www.postgresql.org/docs/current/runtime-config-connection.html#GUC-LISTEN-ADDRESSES).

#### `random_page_cost`

Override PostgreSQL's [`random_page_cost`
setting](https://www.postgresql.org/docs/current/runtime-config-query.html#GUC-RANDOM-PAGE-COST)

#### `replication_primary`

On the [warm standby replicas](postgresql.md#postgresql-warm-standby), set to the
hostname of the primary PostgreSQL server that streaming replication
should be done from.

#### `replication_user`

On the [warm standby replicas](postgresql.md#postgresql-warm-standby), set to the
username that the host should authenticate to the primary PostgreSQL
server as, for streaming replication. Authentication will be done
based on the `pg_hba.conf` file; if you are using password
authentication, you can set a `postgresql_replication_password` secret
for authentication.

#### `skip_backups`

If set to as true value, inhibits the nightly [`wal-g` backups][wal-g] which
would be taken on all non-replicated hosts and [all warm standby
replicas](postgresql.md#postgresql-warm-standby). This is generally only set if you have
multiple warm standby replicas, in order to avoid taking multiple backups, one
per replica.

#### `backups_disk_concurrency`

Number of concurrent disk reads to use when taking backups. Defaults to 1; you
may wish to increase this if you are taking backups on a replica, so can afford
to affect other disk I/O, and have an SSD which is good at parallel random
reads.

#### `backups_directory`

If S3 secrets are not configured, perform daily database backups to this path on
disk instead. It should be owned by the `postgres` user.

This option is not recommended for disaster recovery purposes, since unless the
directory is on a different disk from the database itself, _backups will likely
also be lost if the database is lost._ This setting can be useful if the path is
on a NAS mountpoint, or if some other process copies this data off the disk; or
if backups are purely for point-in-time historical analysis of recent
application-level data changes.

#### `backups_incremental`

The number of delta (incremental) database backups to take between full backups.
Defaults to 0 for S3 backups, and 6 for local-disk backups.

#### `backups_storage_class`

What [storage class](https://aws.amazon.com/s3/storage-classes/) to use when
uploading database backups. Defaults to `STANDARD`, meaning "[S3
standard][s3-standard]", but many deployments will have overall lower costs if
"[S3 Standard - Infrequent Access][s3-ia]" is used, via the `STANDARD_IA`
value. Also supported is "[S3 Reduced Redundancy][s3-rr]", by setting
`REDUCED_REDUNDANCY`, but this is not suggested for production use.

[s3-standard]: https://aws.amazon.com/s3/storage-classes/#General_purpose
[s3-ia]: https://aws.amazon.com/s3/storage-classes/#Infrequent_access
[s3-rr]: https://aws.amazon.com/s3/reduced-redundancy/

#### `missing_dictionaries`

If set to a true value during initial database creation, uses PostgreSQL's
standard `pg_catalog.english` text search configuration, rather than Zulip's
improved set of stopwords. Has no effect after initial database construction.

#### `ssl_ca_file`

Set to the path to the PEM-encoded certificate authority used to
authenticate client connections.

#### `ssl_cert_file`

Set to the path to the PEM-encoded public certificate used to secure
client connections.

#### `ssl_key_file`

Set to the path to the PEM-encoded private key used to secure client
connections.

#### `ssl_mode`

The mode that should be used to verify the server certificate. The
PostgreSQL default is `prefer`, which provides no security benefit; we
strongly suggest setting this to `require` or better if you are using
certificate authentication. See the [PostgreSQL
documentation](https://www.postgresql.org/docs/current/libpq-ssl.html#LIBPQ-SSL-SSLMODE-STATEMENTS)
for potential values.

#### `version`

The version of PostgreSQL that is in use. Do not set by hand; use the
[PostgreSQL upgrade tool](upgrade.md#upgrading-postgresql).

### `[memcached]`

#### `memory`

Override the number of megabytes of memory that memcached should be
configured to consume; defaults to 1/8th of the total server memory.

#### `max_item_size`

Override the maximum size that an item in memcached can store. This defaults to
1m; adjusting it should only be necessary if your Zulip server has organizations
which have more than 20k users.

#### `size_reporting`

Set to a true value to enable object size reporting in memcached. This incurs a
small overhead for every store or delete operation, but allows a
memcached_exporter to report precise item size distribution.

### `[loadbalancer]`

#### `ips`

Comma-separated list of IP addresses or netmasks of external load balancers
whose `X-Forwarded-For` and `X-Forwarded-Proto` should be respected. These can
be individual IP addresses, or CIDR IP address ranges.

### `[http_proxy]`

#### `host`

The hostname or IP address of an [outgoing HTTP `CONNECT`
proxy](deployment.md#customizing-the-outgoing-http-proxy). Defaults to
`localhost` if unspecified.

#### `port`

The TCP port of the HTTP `CONNECT` proxy on the host specified above.
Defaults to `4750` if unspecified.

#### `listen_address`

The IP address that Smokescreen should bind to and listen on.
Defaults to `127.0.0.1`.

#### `enable_for_camo`

Because Camo includes logic to deny access to private subnets, routing
its requests through Smokescreen is generally not necessary. Set to
true or false to override the default, which uses the proxy only if
it is not the default of Smokescreen on a local host.

### `[sentry]`

#### `organization`

The Sentry organization used for the [Sentry deploy hook](deployment.md#sentry-deploy-hook).

#### `project`

The Sentry project used for the [Sentry deploy hook](deployment.md#sentry-deploy-hook).
