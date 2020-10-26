# Deployment options

The default Zulip installation instructions will install a complete
Zulip server, with all of the services it needs, on a single machine.

For production deployment, however, it's common to want to do
something more complicated.  This page documents the options for doing so.

## Installing Zulip from Git

To install a development version of Zulip from Git, just clone the Git
repository from GitHub:

```
# First, install Git if you don't have it installed already
sudo apt install git
git clone https://github.com/zulip/zulip.git zulip-server-git
```

and then
[continue the normal installation instructions](../production/install.html#step-2-install-zulip).
You can also [upgrade Zulip from Git](../production/upgrade-or-modify.html#upgrading-from-a-git-repository).

The most common use case for this is upgrading to `master` to get a
feature that hasn't made it into an official release yet (often
support for a new base OS release).  See [upgrading to
master][upgrade-to-master] for notes on how `master` works and the
support story for it, and [upgrading to future
releases][upgrade-to-future-release] for notes on upgrading Zulip
afterwards.

In particular, we are always very glad to investigate problems with
installing Zulip from `master`; they are rare and help us ensure that
our next major release has a reliable install experience.

[upgrade-to-master]: ../production/upgrade-or-modify.html#upgrading-to-master
[upgrade-to-future-release]: ../production/upgrade-or-modify.html#upgrading-to-future-releases

## Zulip in Docker

Zulip has an officially supported, experimental
[docker image](https://github.com/zulip/docker-zulip).  Please note
that Zulip's [normal installer](../production/install.md) has been
extremely reliable for years, whereas the Docker image is new and has
rough edges, so we recommend the normal installer unless you have a
specific reason to prefer Docker.

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

```
env PUPPET_CLASSES=zulip::profile::redis ./scripts/setup/install
```

All puppet modules under `zulip::profile` are allowed to be configured
stand-alone on a host.  You can see most likely manifests you might
want to choose in the list of includes in [the main manifest for the
default all-in-one Zulip server][standalone.pp], though it's also
possible to subclass some of the lower-level manifests defined in that
directory if you want to customize.  A good example of doing this is
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

Follow the [standard instructions](../production/install.md), with one
change.  When running the installer, pass the `--no-init-db`
flag, e.g.:

```
sudo -s  # If not already root
./zulip-server-*/scripts/setup/install --certbot \
    --email=YOUR_EMAIL --hostname=YOUR_HOSTNAME \
    --no-init-db --postgresql-missing-dictionaries
```

The script also installs and starts PostgreSQL on the server by
default. We don't need it, so run the following command to
stop and disable the local PostgreSQL server.

```
sudo service postgresql stop
sudo update-rc.d postgresql disable
```

This complication will be removed in a future version.

#### Step 2: Create the PostgreSQL database

Access an administrative `psql` shell on your PostgreSQL database, and
run the commands in `scripts/setup/create-db.sql` to:

* Create a database called `zulip`.
* Create a user called `zulip`.
* Now log in with the `zulip` user to create a schema called
  `zulip` in the `zulip` database. You might have to grant `create`
  privileges first for the `zulip` user to do this.

Depending on how authentication works for your PostgreSQL installation,
you may also need to set a password for the Zulip user, generate a
client certificate, or similar; consult the documentation for your
database provider for the available options.

#### Step 3: Configure Zulip to use the PostgreSQL database

In `/etc/zulip/settings.py` on your Zulip server, configure the
following settings with details for how to connect to your PostgreSQL
server.  Your database provider should provide these details.

* `REMOTE_POSTGRES_HOST`: Name or IP address of the PostgreSQL server.
* `REMOTE_POSTGRES_PORT`: Port on the PostgreSQL server.
* `REMOTE_POSTGRES_SSLMODE`: SSL Mode used to connect to the server.

If you're using password authentication, you should specify the
password of the `zulip` user in /etc/zulip/zulip-secrets.conf as
follows:

```
postgres_password = abcd1234
```

Now complete the installation by running the following commands.

```
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

    ```
    [application_server]
    nginx_listen_port = 12345
    ```

1. As root, run
  `/home/zulip/deployments/current/scripts/zulip-puppet-apply`.  This
  will convert Zulip's main `nginx` configuration file to use your new
  port.

We also have documentation for a Zulip server [using HTTP][using-http] for use
behind reverse proxies.

[using-http]: ../production/deployment.html#configuring-zulip-to-allow-http

## Putting the Zulip application behind a reverse proxy

Zulip is designed to support being run behind a reverse proxy server.
This section contains notes on the configuration required with
variable reverse proxy implementations.

### Installer options

If your Zulip server will not be on the public Internet, we recommend,
installing with the `--self-signed-cert` option (rather than the
`--certbot` option), since CertBot requires the server to be on the
public Internet.

#### Configuring Zulip to allow HTTP

Depending on your environment, you may want the reverse proxy to talk
to the Zulip server over HTTP; this can be secure when the Zulip
server is not directly exposed to the public Internet.

After installing the Zulip server as
[described above](#installer-options), you can configure Zulip to talk
HTTP as follows:

1. Add the following block to `/etc/zulip/zulip.conf`:

    ```
    [application_server]
    http_only = true
    ```

1. As root, run
`/home/zulip/deployments/current/scripts/zulip-puppet-apply`.  This
will convert Zulip's main `nginx` configuration file to allow HTTP
instead of HTTPS.

1. Finally, restart the Zulip server, using
`/home/zulip/deployments/current/scripts/restart-server`.

### nginx configuration

For `nginx` configuration, there's two things you need to set up:
* The root `nginx.conf` file.  We recommend using
  `/etc/nginx/nginx.conf` from your Zulip server for our recommended
  settings.  E.g. if you don't set `client_max_body_size`, it won't be
  possible to upload large files to your Zulip server.
* The `nginx` site-specific configuration (in
  `/etc/nginx/sites-available`) for the Zulip app.  You can look at
  our [nginx reverse proxy configuration][nginx-loadbalancer] to see
  an example of how to do this properly (the various include files are
  available via the `zulip::nginx` Puppet module).  Or modify this
  example:

```
server {
        listen                  443 ssl;
        server_name             zulip.example.net;

        ssl                     on;
        ssl_certificate         /path/to/fullchain-cert.pem;
        ssl_certificate_key     /path/to/private-key.pem;

        location / {
                proxy_set_header        X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header        Host $http_host;
                proxy_http_version      1.1;
                proxy_buffering         off;
                proxy_read_timeout      20m;
                proxy_pass              https://zulip-upstream-host;
        }
}
```

Don't forget to update `server_name`, `ssl_certificate`,
`ssl_certificate_key` and `proxy_pass` with the appropriate values for
your installation.

[nginx-proxy-config]: https://github.com/zulip/zulip/blob/master/puppet/zulip/files/nginx/zulip-include-common/proxy
[nginx-proxy-longpolling-config]: https://github.com/zulip/zulip/blob/master/puppet/zulip/files/nginx/zulip-include-common/proxy_longpolling
[standalone.pp]: https://github.com/zulip/zulip/blob/master/puppet/zulip/manifests/profile/standalone.pp
[zulipchat-puppet]: https://github.com/zulip/zulip/tree/master/puppet/zulip_ops/manifests
[nginx-loadbalancer]: https://github.com/zulip/zulip/blob/master/puppet/zulip_ops/files/nginx/sites-available/loadbalancer

### Apache2 configuration

Below is a working example of a full Apache2 configuration. It assumes
that your Zulip sits at `http://localhost:5080`. You first need to
make the following changes in two configuration files.

1. Follow the instructions for [Configure Zulip to allow HTTP](#configuring-zulip-to-allow-http).

2. Add the following to `/etc/zulip/settings.py`:
    ```
    EXTERNAL_HOST = 'zulip.example.com'
    ALLOWED_HOSTS = ['zulip.example.com', '127.0.0.1']
    USE_X_FORWARDED_HOST = True
    ```


3. Restart your Zulip server with `/home/zulip/deployments/current/scripts/restart-server`.

4. Create an Apache2 virtual host configuration file, similar to the
   following.  Place it the appropriate path for your Apache2
   installation and enable it (E.g. if you use Debian or Ubuntu, then
   place it in `/etc/apache2/sites-available/zulip.example.com.conf`
   and then run `a2ensite zulip.example.com && systemctl reload
   apache2`):

    ```
    <VirtualHost *:80>
        ServerName zulip.example.com
        RewriteEngine On
        RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L]
    </VirtualHost>

    <VirtualHost *:443>
      ServerName zulip.example.com

      RequestHeader set "X-Forwarded-Proto" expr=%{REQUEST_SCHEME}
      RequestHeader set "X-Forwarded-SSL" expr=%{HTTPS}

      RewriteEngine On
      RewriteRule /(.*)           http://localhost:5080/$1 [P,L]

      <Location />
        Require all granted
        ProxyPass  http://localhost:5080/  timeout=300
        ProxyPassReverse  http://localhost:5080/
        ProxyPassReverseCookieDomain  127.0.0.1  zulip.example.com
      </Location>

      SSLEngine on
      SSLProxyEngine on
      SSLCertificateFile /etc/letsencrypt/live/zulip.example.com/fullchain.pem
      SSLCertificateKeyFile /etc/letsencrypt/live/zulip.example.com/privkey.pem
      SSLOpenSSLConfCmd DHParameters "/etc/nginx/dhparam.pem"
      SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
      SSLCipherSuite ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384
      SSLHonorCipherOrder off
      SSLSessionTickets off
      Header set Strict-Transport-Security "max-age=31536000"
    </VirtualHost>
    ```

### HAProxy configuration

If you want to use HAProxy with Zulip, this `backend` config is a good
place to start.

```
backend zulip
    mode http
    balance leastconn
    http-request set-header X-Client-IP %[src]
    reqadd X-Forwarded-Proto:\ https
    server zulip 10.10.10.10:80 check
```

Since this configuration uses the `http` mode, you will also need to
[configure Zulip to allow HTTP](#configuring-zulip-to-allow-http) as
described above.

### Other proxies

If you're using another reverse proxy implementation, there are few
things you need to be careful about when configuring it:

1. Configure your reverse proxy (or proxies) to correctly maintain the
`X-Forwarded-For` HTTP header, which is supposed to contain the series
of IP addresses the request was forwarded through.  You can verify
your work by looking at `/var/log/zulip/server.log` and checking it
has the actual IP addresses of clients, not the IP address of the
proxy server.

2. Ensure your proxy doesn't interfere with Zulip's use of
long-polling for real-time push from the server to your users'
browsers.  This [nginx code snippet][nginx-proxy-longpolling-config]
does this.

The key configuration options are, for the `/json/events` and
`/api/1/events` endpoints:

* `proxy_read_timeout 1200;`.  It's critical that this be
  significantly above 60s, but the precise value isn't important.
* `proxy_buffering off`.  If you don't do this, your `nginx` proxy may
  return occasional 502 errors to clients using Zulip's events API.

3. The other tricky failure mode we've seen with `nginx` reverse
proxies is that they can load-balance between the IPv4 and IPv6
addresses for a given hostname.  This can result in mysterious errors
that can be quite difficult to debug.  Be sure to declare your
`upstreams` equivalent in a way that won't do load-balancing
unexpectedly (e.g. pointing to a DNS name that you haven't configured
with multiple IPs for your Zulip machine; sometimes this happens with
IPv6 configuration).


## System and deployment configuration

The file `/etc/zulip/zulip.conf` is used to configure properties of
the system and deployment; `/etc/zulip/settings.py` is used to
configure the application itself.  The `zulip.conf` sections and
settings are described below.

### `[machine]`

#### `puppet_classes`

A comma-separated list of the Puppet classes to install on the server.
The most common is **`zulip::profile::standalone`**, used for a
stand-alone single-host deployment.
[Components](../overview/architecture-overview.html#components) of
that include:
 - **`zulip::profile::app_frontend`**
 - **`zulip::profile::memcached`**
 - **`zulip::profile::postgresql`**
 - **`zulip::profile::redis`**
 - **`zulip::profile::rabbitmq`**

If you are using a [Apache as a single-sign-on
authenticator](../production/authentication-methods.html#apache-based-sso-with-remote-user),
you will need to add **`zulip::apache_sso`** to the list.

#### `pgroonga`

Set to the string `enabled` if enabling the [multi-language PGroonga
search
extension](../subsystems/full-text-search.html#multi-language-full-text-search).



### `[deployment]`

#### `deploy_options`

Options passed by `upgrade-zulip` and `upgrade-zulip-from-git` into
`upgrade-zulip-stage-2`.  These might be any of:

 - **`--skip-puppet`** skips doing Puppet/apt upgrades.  The user will need
   to run `zulip-puppet-apply` manually after the upgrade.
 - **`--skip-migrations`** skips running database migrations.  The
   user will need to run `./manage.py migrate` manually after the upgrade.
 - **`--skip-purge-old-deployments`** skips purging old deployments;
   without it, only deployments with the last two weeks are kept.

Generally installations will not want to set any of these options; the
`--skip-*` options are primarily useful for reducing upgrade downtime
for servers that are upgraded frequently by core Zulip developers.

#### `git_repo_url`

Default repository URL used when [upgrading from a Git
repository](../production/upgrade-or-modify.html#upgrading-from-a-git-repository).



### `[application_server]`

#### `http_only`

If set to non-empty, [configures Zulip to allow HTTP
access][using-http]; use if Zulip is deployed behind a reverse proxy
that is handling SSL/TLS termination.

#### `nginx_listen_port`

Set to the port number if you [prefer to listen on a port other than
443](#using-an-alternate-port).

#### `no_serve_uploads`

To enable the [the S3 uploads backend][s3-uploads], one needs to both
configure `settings.py` and set this to 'true' to configure
`nginx`. Remove this field to return to the local uploads backend (any
non-empty value is currently equivalent to true).

[s3-uploads]: ../production/upload-backends.html#s3-backend-configuration

#### `uwsgi_buffer_size`

Override the default uwsgi buffer size of 8192.

#### `uwsgi_listen_backlog_limit`

Override the default uwsgi backlog of 128 connections.

#### `uwsgi_processes`

Override the default `uwsgi` (Django) process count of 6 on hosts with
more than 3.5GiB of RAM, 4 on hosts with less.



### `[certbot]`

#### `auto_renew`

If set to the string `yes`, [Certbot will attempt to automatically
renew its certificate](../production/ssl-certificates.html#certbot-recommended).  Do
no set by hand; use `scripts/setup/setup-certbot` to configure this.



### `[postfix]`

#### `mailname`

The hostname that [Postfix should be configured to receive mail
at](../production/email-gateway.html#local-delivery-setup).

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

#### `replication`

Set to non-empty to enable replication to enable [streaming
replication between PostgreSQL
servers](../production/export-and-import.html#postgresql-streaming-replication).

#### `ssl_ca_file`

Set to the path to the PEM-encoded certificate authority used to
authenticate client connections.

#### `ssl_cert_file`

Set to the path to the PEM-encoded public certificate used to secure
client connections.

#### `ssl_key_file`

Set to the path to the PEM-encoded private key used to secure client
connections.

#### `version`

The version of PostgreSQL that is in use.  Do not set by hand; use the
[PostgreSQL upgrade tool](../production/upgrade-or-modify.html#upgrading-postgresql).



### `[rabbitmq]`

#### `nodename`

The name used to identify the local RabbitMQ server; do not modify.



### `[memcached]`

#### `memory`

Override the number of megabytes of memory that memcached should be
configured to consume; defaults to 1/8th of the total server memory.



### `[loadbalancer]`

#### `ips`

Comma-separated list of IP addresses or netmasks of external
load balancers whose `X-Forwarded-For` should be respected.
