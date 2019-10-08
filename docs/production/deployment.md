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
You can also [upgrade Zulip from Git](../production/maintain-secure-upgrade.html#upgrading-from-a-git-repository).

## Zulip in Docker

Zulip has an officially supported, experimental
[docker image](https://github.com/zulip/docker-zulip).  Please note
that Zulip's [normal installer](../production/install.html) has been
extremely reliable for years, whereas the Docker image is new and has
rough edges, so we recommend the normal installer unless you have a
specific reason to prefer Docker.

## Running Zulip's service dependencies on different machines

Zulip has full support for each top-level service living on its own
machine.

You can configure remote servers for Postgres, RabbitMQ, Redis,
in `/etc/zulip/settings.py`; just search for the service name in that
file and you'll find inline documentation in comments for how to
configure it.

Since some of these services require some configuration on the node
itself (e.g. installing our `postgres` extensions), we have designed
the puppet configuration that Zulip uses for installing and upgrading
configuration to be completely modular.

For example, you can install a Zulip rabbitmq server on a machine, you
can do the following after unpacking a Zulip production release
tarball:

```
env PUPPET_CLASSES=zulip::redis ./scripts/setup/install
```

You can see most likely manifests you might want to choose in the list
of includes in
[the main manifest for the default all-in-one Zulip server][voyager.pp],
though it's also possible to subclass some of the lower-level
manifests defined in that directory if you want to customize.  A good
example of doing this is in the
[zulip_ops puppet configuration][zulipchat-puppet] that we use as part
of managing chat.zulip.org and zulipchat.com.

### Using Zulip with Amazon RDS as the database

Unfortunately, you cannot use most third-party database-as-a-service
provides like Amazon RDS as the database provider with Zulip without a
degraded experience.  Zulip let you choose one of two
[full-text search postgres extensions](../subsystems/full-text-search.html).
Neither is available in Amazon RDS.  As a result, if you use one of
those providers, Zulip's full-text search will be unavailable.

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

You can look at our
[nginx reverse proxy configuration][nginx-loadbalancer] to see an
example of how to do this properly (the various include files are
available via the `zulip::nginx` puppet module).  Or modify this example:

```
map $http_upgrade $connection_upgrade {
        default upgrade;
        ''      close;
}
server {
        listen                  443 ssl;
        server_name             zulip.example.net;

        ssl                     on;
        ssl_certificate         /path/to/fullchain-cert.pem;
        ssl_certificate_key     /path/to/private-key.pem;

        location / {
                proxy_set_header        X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header        Host $http_host;
                proxy_set_header        Upgrade $http_upgrade;
                proxy_set_header        Connection $connection_upgrade;
                proxy_http_version      1.1;
                proxy_buffering         off;
                proxy_read_timeout      20m;
                proxy_pass              https://zulip-upstream-host;
        }
}
```

Don't forget to update `server_name`, `ssl_certificate`,
`ssl_certificate_key` and `proxy_pass` with propper values.

[nginx-proxy-config]: https://github.com/zulip/zulip/blob/master/puppet/zulip/files/nginx/zulip-include-common/proxy
[nginx-proxy-longpolling-config]: https://github.com/zulip/zulip/blob/master/puppet/zulip/files/nginx/zulip-include-common/proxy_longpolling
[voyager.pp]: https://github.com/zulip/zulip/blob/master/puppet/zulip/manifests/voyager.pp
[zulipchat-puppet]: https://github.com/zulip/zulip/tree/master/puppet/zulip_ops/manifests
[nginx-loadbalancer]: https://github.com/zulip/zulip/blob/master/puppet/zulip_ops/files/nginx/sites-available/loadbalancer

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
