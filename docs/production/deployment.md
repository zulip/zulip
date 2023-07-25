# Deployment options

The default Zulip installation instructions will install a complete
Zulip server, with all of the services it needs, on a single machine.

For production deployment, however, it's common to want to do
something more complicated. This page documents the options for doing so.

## Installing Zulip from Git

To install a development version of Zulip from Git, just clone the Git
repository from GitHub:

```bash
# First, install Git if you don't have it installed already
sudo apt install git
git clone https://github.com/zulip/zulip.git zulip-server-git
```

and then
[continue the normal installation instructions](install.md#step-2-install-zulip).
You can also [upgrade Zulip from Git](upgrade.md#upgrading-from-a-git-repository).

The most common use case for this is upgrading to `main` to get a
feature that hasn't made it into an official release yet (often
support for a new base OS release). See [upgrading to
main][upgrade-to-main] for notes on how `main` works and the
support story for it, and [upgrading to future
releases][upgrade-to-future-release] for notes on upgrading Zulip
afterwards.

In particular, we are always very glad to investigate problems with
installing Zulip from `main`; they are rare and help us ensure that
our next major release has a reliable install experience.

[upgrade-to-main]: modify.md#upgrading-to-main
[upgrade-to-future-release]: modify.md#upgrading-to-future-releases

## Zulip in Docker

Zulip has an officially supported, experimental
[docker image](https://github.com/zulip/docker-zulip). Please note
that Zulip's [normal installer](install.md) has been
extremely reliable for years, whereas the Docker image is new and has
rough edges, so we recommend the normal installer unless you have a
specific reason to prefer Docker.

## Advanced installer options

The Zulip installer supports the following advanced installer options
as well as those mentioned in the
[install](install.md#installer-options) documentation:

- `--postgresql-version`: Sets the version of PostgreSQL that will be
  installed. We currently support PostgreSQL 12, 13, 14, and 15, with 15 being
  the default.

- `--postgresql-database-name=exampledbname`: With this option, you
  can customize the default database name. If you do not set this. The
  default database name will be `zulip`. This setting can only be set
  on the first install.

- `--postgresql-database-user=exampledbuser`: With this option, you
  can customize the default database user. If you do not set this. The
  default database user will be `zulip`. This setting can only be set
  on the first install.

- `--postgresql-missing-dictionaries`: Set
  `postgresql.missing_dictionaries` ([docs][missing-dicts]) in the
  Zulip settings, which omits some configuration needed for full-text
  indexing. This should be used with [cloud managed databases like
  RDS](#using-zulip-with-amazon-rds-as-the-database). This option
  conflicts with `--no-overwrite-settings`.

- `--no-init-db`: This option instructs the installer to not do any
  database initialization. This should be used when you already have a
  Zulip database.

- `--no-overwrite-settings`: This option preserves existing
  `/etc/zulip` configuration files.

[missing-dicts]: #missing_dictionaries

## Installing on an existing server

Zulip's installation process assumes it is the only application
running on the server; though installing alongside other applications
is not recommended, we do have [some notes on the
process](install-existing-server.md).

## Deployment hooks

Zulip's upgrades have a hook system which allows for arbitrary
user-configured actions to run before and after an upgrade; see the
[upgrading documentation](upgrade.md#deployment-hooks) for details on
how to write your own.

### Zulip message deploy hook

Zulip can use its deploy hooks to send a message immediately before and after
conducting an upgrade. To configure this:

1. Add `, zulip::hooks::zulip_notify` to the `puppet_classes` line in
   `/etc/zulip/zulip.conf`
1. Add a `[zulip_notify]` section to `/etc/zulip/zulip.conf`:
   ```ini
   [zulip_notify]
   bot_email = your-bot@zulip.example.com
   server = zulip.example.com
   stream = deployments
   ```
1. Add the [api key](https://zulip.com/api/api-keys#get-a-bots-api-key) for the
   bot user in `/etc/zulip/zulip-secrets.conf` as `zulip_release_api_key`:
   ```ini
   # Replace with your own bot's token, found in the Zulip UI
   zulip_release_api_key = abcd1234E6DK0F7pNSqaMSuzd8C5i7Eu
   ```
1. As root, run `/home/zulip/deployments/current/scripts/zulip-puppet-apply`.

### Sentry deploy hook

Zulip can use its deploy hooks to create [Sentry
releases][sentry-release], which can help associate Sentry [error
logging][sentry-error] with specific releases. If you are deploying
Zulip from Git, it can be aware of which Zulip commits are associated
with the release, and help identify which commits might be relevant to
an error.

To do so:

1. Enable [Sentry error logging][sentry-error].
2. Add a new [internal Sentry integration][sentry-internal] named
   "Release annotator".
3. Grant the internal integration the [permissions][sentry-perms] of
   "Admin" on "Release".
4. Add `, zulip::hooks::sentry` to the `puppet_classes` line in `/etc/zulip/zulip.conf`
5. Add a `[sentry]` section to `/etc/zulip/zulip.conf`:
   ```ini
   [sentry]
   organization = your-organization-name
   project = your-project-name
   ```
6. Add the [authentication token][sentry-tokens] for your internal Sentry integration
   to your `/etc/zulip/zulip-secrets.conf`:
   ```ini
   # Replace with your own token, found in Sentry
   sentry_release_auth_token = 6c12f890c1c864666e64ee9c959c4552b3de473a076815e7669f53793fa16afc
   ```
7. As root, run `/home/zulip/deployments/current/scripts/zulip-puppet-apply`.

If you are deploying Zulip from Git, you will also need to:

1. In your Zulip project, add the [GitHub integration][sentry-github].
2. Configure the `zulip/zulip` GitHub project for your Sentry project.
   You should do this even if you are deploying a private fork of
   Zulip.
3. Additionally grant the internal integration "Read & Write" on
   "Organization"; this is necessary to associate the commits with the
   release.

[sentry-release]: https://docs.sentry.io/product/releases/
[sentry-error]: ../subsystems/logging.md#sentry-error-logging
[sentry-github]: https://docs.sentry.io/product/integrations/source-code-mgmt/github/
[sentry-internal]: https://docs.sentry.io/product/integrations/integration-platform/internal-integration/
[sentry-perms]: https://docs.sentry.io/product/integrations/integration-platform/#permissions
[sentry-tokens]: https://docs.sentry.io/product/integrations/integration-platform/internal-integration#auth-tokens

## Running Zulip's service dependencies on different machines

Zulip has full support for each top-level service living on its own
machine.

You can configure remote servers for PostgreSQL, RabbitMQ, Redis,
in `/etc/zulip/settings.py`; just search for the service name in that
file and you'll find inline documentation in comments for how to
configure it.

Since some of these services require some configuration on the node
itself (e.g. installing our PostgreSQL extensions), we have designed
the Puppet configuration that Zulip uses for installing and upgrading
configuration to be completely modular.

For example, to install a Zulip Redis server on a machine, you can run
the following after unpacking a Zulip production release tarball:

```bash
env PUPPET_CLASSES=zulip::profile::redis ./scripts/setup/install
```

All puppet modules under `zulip::profile` are allowed to be configured
stand-alone on a host. You can see most likely manifests you might
want to choose in the list of includes in [the main manifest for the
default all-in-one Zulip server][standalone.pp], though it's also
possible to subclass some of the lower-level manifests defined in that
directory if you want to customize. A good example of doing this is
in the [zulip_ops Puppet configuration][zulipchat-puppet] that we use
as part of managing chat.zulip.org and zulip.com.

### Using Zulip with Amazon RDS as the database

You can use DBaaS services like Amazon RDS for the Zulip database.
The experience is slightly degraded, in that most DBaaS provides don't
include useful dictionary files in their installations and don't
provide a way to provide them yourself, resulting in a degraded
[full-text search](../subsystems/full-text-search.md) experience
around issues dictionary files are relevant (e.g. stemming).

You also need to pass some extra options to the Zulip installer in
order to avoid it throwing an error when Zulip attempts to configure
the database's dictionary files for full-text search; the details are
below.

#### Step 1: Set up Zulip

Follow the [standard instructions](install.md), with one
change. When running the installer, pass the `--no-init-db`
flag, e.g.:

```bash
sudo -s  # If not already root
./zulip-server-*/scripts/setup/install --certbot \
    --email=YOUR_EMAIL --hostname=YOUR_HOSTNAME \
    --no-init-db --postgresql-missing-dictionaries
```

The script also installs and starts PostgreSQL on the server by
default. We don't need it, so run the following command to
stop and disable the local PostgreSQL server.

```bash
sudo service postgresql stop
sudo update-rc.d postgresql disable
```

This complication will be removed in a future version.

#### Step 2: Create the PostgreSQL database

Access an administrative `psql` shell on your PostgreSQL database, and
run the commands in `scripts/setup/create-db.sql` to:

- Create a database called `zulip`.
- Create a user called `zulip`.
- Now log in with the `zulip` user to create a schema called
  `zulip` in the `zulip` database. You might have to grant `create`
  privileges first for the `zulip` user to do this.

Depending on how authentication works for your PostgreSQL installation,
you may also need to set a password for the Zulip user, generate a
client certificate, or similar; consult the documentation for your
database provider for the available options.

#### Step 3: Configure Zulip to use the PostgreSQL database

In `/etc/zulip/settings.py` on your Zulip server, configure the
following settings with details for how to connect to your PostgreSQL
server. Your database provider should provide these details.

- `REMOTE_POSTGRES_HOST`: Name or IP address of the PostgreSQL server.
- `REMOTE_POSTGRES_PORT`: Port on the PostgreSQL server.
- `REMOTE_POSTGRES_SSLMODE`: SSL Mode used to connect to the server.

If you're using password authentication, you should specify the
password of the `zulip` user in /etc/zulip/zulip-secrets.conf as
follows:

```ini
postgres_password = abcd1234
```

Now complete the installation by running the following commands.

```bash
# Ask Zulip installer to initialize the PostgreSQL database.
su zulip -c '/home/zulip/deployments/current/scripts/setup/initialize-database'

# And then generate a realm creation link:
su zulip -c '/home/zulip/deployments/current/manage.py generate_realm_creation_link'
```

## Using an alternate port

If you'd like your Zulip server to use an HTTPS port other than 443, you can
configure that as follows:

1. Edit `EXTERNAL_HOST` in `/etc/zulip/settings.py`, which controls how
   the Zulip server reports its own URL, and restart the Zulip server
   with `/home/zulip/deployments/current/scripts/restart-server`.
1. Add the following block to `/etc/zulip/zulip.conf`:

   ```ini
   [application_server]
   nginx_listen_port = 12345
   ```

1. As root, run
   `/home/zulip/deployments/current/scripts/zulip-puppet-apply`. This
   will convert Zulip's main `nginx` configuration file to use your new
   port.

We also have documentation for a Zulip server [using HTTP][using-http] for use
behind reverse proxies.

[using-http]: #configuring-zulip-to-allow-http

## Customizing the outgoing HTTP proxy

To protect against [SSRF][ssrf], Zulip 4.8 and above default to
routing all outgoing HTTP and HTTPS traffic through
[Smokescreen][smokescreen], an HTTP `CONNECT` proxy; this includes
outgoing webhooks, website previews, and mobile push notifications.
By default, the Camo image proxy will be automatically configured to
use a custom outgoing proxy, but does not use Smokescreen by default
because Camo includes similar logic to deny access to private
subnets. You can [override][proxy.enable_for_camo] this default
configuration if desired.

To use a custom outgoing proxy:

1. Add the following block to `/etc/zulip/zulip.conf`, substituting in
   your proxy's hostname/IP and port:

   ```ini
   [http_proxy]
   host = 127.0.0.1
   port = 4750
   ```

1. As root, run
   `/home/zulip/deployments/current/scripts/zulip-puppet-apply`. This
   will reconfigure and restart Zulip.

If you have a deployment with multiple frontend servers, or wish to
install Smokescreen on a separate host, you can apply the
`zulip::profile::smokescreen` Puppet class on that host, and follow
the above steps, setting the `[http_proxy]` block to point to that
host.

If you wish to disable the outgoing proxy entirely, follow the above
steps, configuring an empty `host` value.

Optionally, you can also configure the [Smokescreen ACL
list][smokescreen-acls]. By default, Smokescreen denies access to all
[non-public IP
addresses](https://en.wikipedia.org/wiki/Private_network), including
127.0.0.1, but allows traffic to all public Internet hosts.

In Zulip 4.7 and older, to enable SSRF protection via Smokescreen, you
will need to explicitly add the `zulip::profile::smokescreen` Puppet
class, and configure the `[http_proxy]` block as above.

[proxy.enable_for_camo]: #enable_for_camo
[smokescreen]: https://github.com/stripe/smokescreen
[smokescreen-acls]: https://github.com/stripe/smokescreen#acls
[ssrf]: https://owasp.org/www-community/attacks/Server_Side_Request_Forgery

### S3 file storage requests and outgoing proxies

By default, the [S3 file storage backend][s3] bypasses the Smokescreen
proxy, because when running on EC2 it may require metadata from the
IMDS metadata endpoint, which resides on the internal IP address
169.254.169.254 and would thus be blocked by Smokescreen.

If your S3-compatible storage backend requires use of Smokescreen or
some other proxy, you can override this default by setting
`S3_SKIP_PROXY = False` in `/etc/zulip/settings.py`.

[s3]: upload-backends.md#s3-backend-configuration

## Putting the Zulip application behind a reverse proxy

Zulip is designed to support being run behind a reverse proxy server.
This section contains notes on the configuration required with
variable reverse proxy implementations.

### Installer options

If your Zulip server will not be on the public Internet, we recommend,
installing with the `--self-signed-cert` option (rather than the
`--certbot` option), since Certbot requires the server to be on the
public Internet.

#### Configuring Zulip to allow HTTP

Zulip requires clients to connect to Zulip servers over the secure
HTTPS protocol; the insecure HTTP protocol is not supported. However,
we do support using a reverse proxy that speaks HTTPS to clients and
connects to the Zulip server over HTTP; this can be secure when the
Zulip server is not directly exposed to the public Internet.

After installing the Zulip server as [described
above](#installer-options), you can configure Zulip to accept HTTP
requests from a reverse proxy as follows:

1. Add the following block to `/etc/zulip/zulip.conf`:

   ```ini
   [application_server]
   http_only = true
   ```

1. As root, run
   `/home/zulip/deployments/current/scripts/zulip-puppet-apply`. This
   will convert Zulip's main `nginx` configuration file to allow HTTP
   instead of HTTPS.

1. Finally, restart the Zulip server, using
   `/home/zulip/deployments/current/scripts/restart-server`.

Note that Zulip must be able to accurately determine if its connection to the
client was over HTTPS or not; if you enable `http_only`, it is very important
that you correctly configure Zulip to trust the `X-Forwarded-Proto` header from
its proxy (see the next section), or clients may see infinite redirects.

#### Configuring Zulip to trust proxies

Before placing Zulip behind a reverse proxy, it needs to be configured to trust
the client IP addresses that the proxy reports via the `X-Forwarded-For` header,
and the protocol reported by the `X-Forwarded-Proto` header. This is important
to have accurate IP addresses in server logs, as well as in notification emails
which are sent to end users. Zulip doesn't default to trusting all
`X-Forwarded-*` headers, because doing so would allow clients to spoof any IP
address, and claim connections were over a secure connection when they were not;
we specify which IP addresses are the Zulip server's incoming proxies, so we
know which `X-Forwarded-*` headers to trust.

1. Determine the IP addresses of all reverse proxies you are setting up, as seen
   from the Zulip host. Depending on your network setup, these may not be the
   same as the public IP addresses of the reverse proxies. These can also be IP
   address ranges, as expressed in CIDR notation.

1. Add the following block to `/etc/zulip/zulip.conf`.

   ```ini
   [loadbalancer]
   # Use the IP addresses you determined above, separated by commas.
   ips = 192.168.0.100
   ```

1. Reconfigure Zulip with these settings. As root, run
   `/home/zulip/deployments/current/scripts/zulip-puppet-apply`. This will
   adjust Zulip's `nginx` configuration file to accept the `X-Forwarded-For`
   header when it is sent from one of the reverse proxy IPs.

1. Finally, restart the Zulip server, using
   `/home/zulip/deployments/current/scripts/restart-server`.

### nginx configuration

Below is a working example of a full nginx configuration. It assumes
that your Zulip server sits at `https://10.10.10.10:443`; see
[above](#configuring-zulip-to-allow-http) to switch to HTTP.

1. Follow the instructions to [configure Zulip to trust
   proxies](#configuring-zulip-to-trust-proxies).

1. Configure the root `nginx.conf` file. We recommend using
   `/etc/nginx/nginx.conf` from your Zulip server for our recommended
   settings. E.g. if you don't set `client_max_body_size`, it won't be
   possible to upload large files to your Zulip server.

1. Configure the `nginx` site-specific configuration (in
   `/etc/nginx/sites-available`) for the Zulip app. The following
   example is a good starting point:

   ```nginx
   server {
           listen 80;
           listen [::]:80;
           location / {
                   return 301 https://$host$request_uri;
           }
   }

   server {
           listen                  443 ssl http2;
           listen                  [::]:443 ssl http2;
           server_name             zulip.example.com;

           ssl_certificate         /etc/letsencrypt/live/zulip.example.com/fullchain.pem;
           ssl_certificate_key     /etc/letsencrypt/live/zulip.example.com/privkey.pem;

           location / {
                   proxy_set_header        X-Forwarded-For $proxy_add_x_forwarded_for;
                   proxy_set_header        X-Forwarded-Proto $scheme;
                   proxy_set_header        Host $host;
                   proxy_http_version      1.1;
                   proxy_buffering         off;
                   proxy_read_timeout      20m;
                   proxy_pass              https://10.10.10.10:443;
           }
   }
   ```

   Don't forget to update `server_name`, `ssl_certificate`,
   `ssl_certificate_key` and `proxy_pass` with the appropriate values
   for your deployment.

[nginx-proxy-longpolling-config]: https://github.com/zulip/zulip/blob/main/puppet/zulip/files/nginx/zulip-include-common/proxy_longpolling
[standalone.pp]: https://github.com/zulip/zulip/blob/main/puppet/zulip/manifests/profile/standalone.pp
[zulipchat-puppet]: https://github.com/zulip/zulip/tree/main/puppet/zulip_ops/manifests

### Apache2 configuration

Below is a working example of a full Apache2 configuration. It assumes
that your Zulip server sits at `https://internal.zulip.hostname:443`.
Note that if you wish to use SSL to connect to the Zulip server,
Apache requires you use the hostname, not the IP address; see
[above](#configuring-zulip-to-allow-http) to switch to HTTP.

1. Follow the instructions to [configure Zulip to trust
   proxies](#configuring-zulip-to-trust-proxies).

1. Set `USE_X_FORWARDED_HOST = True` in `/etc/zulip/settings.py` and
   restart Zulip.

1. Enable some required Apache modules:

   ```bash
   a2enmod ssl proxy proxy_http headers rewrite
   ```

1. Create an Apache2 virtual host configuration file, similar to the
   following. Place it the appropriate path for your Apache2
   installation and enable it (E.g. if you use Debian or Ubuntu, then
   place it in `/etc/apache2/sites-available/zulip.example.com.conf`
   and then run
   `a2ensite zulip.example.com && systemctl reload apache2`):

   ```apache
   <VirtualHost *:80>
       ServerName zulip.example.com
       RewriteEngine On
       RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L]
   </VirtualHost>

   <VirtualHost *:443>
     ServerName zulip.example.com

     RequestHeader set "X-Forwarded-Proto" expr=%{REQUEST_SCHEME}

     RewriteEngine On
     RewriteRule /(.*)           https://internal.zulip.hostname:443/$1 [P,L]

     <Location />
       Require all granted
       ProxyPass https://internal.zulip.hostname:443/ timeout=1200
     </Location>

     SSLEngine on
     SSLProxyEngine on
     SSLCertificateFile /etc/letsencrypt/live/zulip.example.com/fullchain.pem
     SSLCertificateKeyFile /etc/letsencrypt/live/zulip.example.com/privkey.pem
     # This file can be found in ~zulip/deployments/current/puppet/zulip/files/nginx/dhparam.pem
     SSLOpenSSLConfCmd DHParameters "/etc/nginx/dhparam.pem"
     SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
     SSLCipherSuite ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384
     SSLHonorCipherOrder off
     SSLSessionTickets off
     Header set Strict-Transport-Security "max-age=31536000"
   </VirtualHost>
   ```

   Don't forget to update `ServerName`, `RewriteRule`, `ProxyPass`,
   `SSLCertificateFile`, and `SSLCertificateKeyFile` as are
   appropriate for your deployment.

### HAProxy configuration

Below is a working example of a HAProxy configuration. It assumes that
your Zulip server sits at `https://10.10.10.10:443`see
[above](#configuring-zulip-to-allow-http) to switch to HTTP.

1. Follow the instructions to [configure Zulip to trust
   proxies](#configuring-zulip-to-trust-proxies).

1. Configure HAProxy. The below is a minimal `frontend` and `backend`
   configuration:

   ```text
   frontend zulip
       mode http
       bind *:80
       bind *:443 ssl crt /etc/ssl/private/zulip-combined.crt
       http-request redirect scheme https code 301 unless { ssl_fc }
       http-request set-header X-Forwarded-Proto http unless { ssl_fc }
       http-request set-header X-Forwarded-Proto https if { ssl_fc }
       default_backend zulip

   backend zulip
       mode http
       timeout server 20m
       server zulip 10.10.10.10:443 check ssl ca-file /etc/ssl/certs/ca-certificates.crt
   ```

   Don't forget to update `bind *:443 ssl crt` and `server` as is
   appropriate for your deployment.

### Other proxies

If you're using another reverse proxy implementation, there are few
things you need to be careful about when configuring it:

1. Configure your reverse proxy (or proxies) to correctly maintain the
   `X-Forwarded-For` HTTP header, which is supposed to contain the series
   of IP addresses the request was forwarded through. Additionally,
   [configure Zulip to respect the addresses sent by your reverse
   proxies](#configuring-zulip-to-trust-proxies). You can verify
   your work by looking at `/var/log/zulip/server.log` and checking it
   has the actual IP addresses of clients, not the IP address of the
   proxy server.

1. Configure your reverse proxy (or proxies) to correctly maintain the
   `X-Forwarded-Proto` HTTP header, which is supposed to contain either `https`
   or `http` depending on the connection between your browser and your
   proxy. This will be used by Django to perform CSRF checks regardless of your
   connection mechanism from your proxy to Zulip. Note that the proxies _must_
   set the header, overriding any existing values, not add a new header.

1. Configure your proxy to pass along the `Host:` header as was sent
   from the client, not the internal hostname as seen by the proxy.
   If this is not possible, you can set `USE_X_FORWARDED_HOST = True`
   in `/etc/zulip/settings.py`, and pass the client's `Host` header to
   Zulip in an `X-Forwarded-Host` header.

1. Ensure your proxy doesn't interfere with Zulip's use of
   long-polling for real-time push from the server to your users'
   browsers. This [nginx code snippet][nginx-proxy-longpolling-config]
   does this.

   The key configuration options are, for the `/json/events` and
   `/api/1/events` endpoints:

   - `proxy_read_timeout 1200;`. It's critical that this be
     significantly above 60s, but the precise value isn't important.
   - `proxy_buffering off`. If you don't do this, your `nginx` proxy may
     return occasional 502 errors to clients using Zulip's events API.

1. The other tricky failure mode we've seen with `nginx` reverse
   proxies is that they can load-balance between the IPv4 and IPv6
   addresses for a given hostname. This can result in mysterious errors
   that can be quite difficult to debug. Be sure to declare your
   `upstreams` equivalent in a way that won't do load-balancing
   unexpectedly (e.g. pointing to a DNS name that you haven't configured
   with multiple IPs for your Zulip machine; sometimes this happens with
   IPv6 configuration).

## PostgreSQL warm standby

Zulip's configuration allows for [warm standby database
replicas][warm-standby] as a disaster recovery solution; see the
linked PostgreSQL documentation for details on this type of
deployment. Zulip's configuration builds on top of `wal-g`, our
[streaming database backup solution][wal-g], and thus requires that it
be configured for the primary and all secondary warm standby replicas.

In addition to having `wal-g` backups configured, warm standby
replicas should configure the hostname of their primary replica, and
username to use for replication, in `/etc/zulip/zulip.conf`:

```ini
[postgresql]
replication_user = replicator
replication_primary = hostname-of-primary.example.com
```

The `postgres` user on the replica will need to be able to
authenticate as the `replication_user` user, which may require further
configuration of `pg_hba.conf` and client certificates on the replica.
If you are using password authentication, you can set a
`postgresql_replication_password` secret in
`/etc/zulip/zulip-secrets.conf`.

[warm-standby]: https://www.postgresql.org/docs/current/warm-standby.html
[wal-g]: export-and-import.md#database-only-backup-tools

## System and deployment configuration

The file `/etc/zulip/zulip.conf` is used to configure properties of
the system and deployment; `/etc/zulip/settings.py` is used to
[configure the application itself](settings.md). The `zulip.conf`
sections and settings are described below.

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
- **`zulip::profile::redis`**
- **`zulip::profile::rabbitmq`**

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
443](#using-an-alternate-port).

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

On the [warm standby replicas](#postgresql-warm-standby), set to the
hostname of the primary PostgreSQL server that streaming replication
should be done from.

#### `replication_user`

On the [warm standby replicas](#postgresql-warm-standby), set to the
username that the host should authenticate to the primary PostgreSQL
server as, for streaming replication. Authentication will be done
based on the `pg_hba.conf` file; if you are using password
authentication, you can set a `postgresql_replication_password` secret
for authentication.

#### `skip_backups`

If set to as true value, inhibits the nightly [`wal-g` backups][wal-g] which
would be taken on all non-replicated hosts and [all warm standby
replicas](#postgresql-warm-standby). This is generally only set if you have
multiple warm standby replicas, in order to avoid taking multiple backups, one
per replica.

#### `backups_disk_concurrency`

Number of concurrent disk reads to use when taking backups. Defaults to 1; you
may wish to increase this if you are taking backups on a replica, so can afford
to affect other disk I/O, and have an SSD which is good at parallel random
reads.

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

### `[loadbalancer]`

#### `ips`

Comma-separated list of IP addresses or netmasks of external load balancers
whose `X-Forwarded-For` and `X-Forwarded-Proto` should be respected. These can
be individual IP addresses, or CIDR IP address ranges.

### `[http_proxy]`

#### `host`

The hostname or IP address of an [outgoing HTTP `CONNECT`
proxy](#customizing-the-outgoing-http-proxy). Defaults to `localhost`
if unspecified.

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

The Sentry organization used for the [Sentry deploy hook](#sentry-deploy-hook).

#### `project`

The Sentry project used for the [Sentry deploy hook](#sentry-deploy-hook).
