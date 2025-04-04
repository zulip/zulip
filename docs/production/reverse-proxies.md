## Reverse proxies

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
   settings. E.g., if you don't set `client_max_body_size`, it won't be
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
   installation and enable it (e.g., if you use Debian or Ubuntu, then
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
your Zulip server sits at `https://10.10.10.10:443`; see
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

   If your proxy _cannot_ set the `X-Forwarded-Proto` header, you can opt to do
   all HTTP-to-HTTPS redirection at the load-balancer level, and set
   [`loadbalancer.rejects_http_requests` in `zulip.conf`][no-proto-header]; but
   note the important security caveats for that in its documentation.

1. Configure your proxy to pass along the `Host:` header as was sent
   from the client, not the internal hostname as seen by the proxy.
   If this is not possible, you can set `USE_X_FORWARDED_HOST = True`
   in `/etc/zulip/settings.py`, and pass the client's `Host` header to
   Zulip in an `X-Forwarded-Host` header.

1. Ensure your proxy doesn't interfere with Zulip's use of
   long-polling for real-time push from the server to your users'
   browsers. This [nginx code snippet][nginx-proxy-longpolling-config]
   does this.

   The key configuration options are:

   - `proxy_read_timeout 1200;`. It's critical that this be significantly above
     60s, but the precise value isn't important. This is most important for the
     events API, but must be applied to all endpoints.
   - `proxy_buffering off`. If you don't do this, your `nginx` proxy may return
     occasional 502 errors to clients using Zulip's events API.

1. The other tricky failure mode we've seen with `nginx` reverse
   proxies is that they can load-balance between the IPv4 and IPv6
   addresses for a given hostname. This can result in mysterious errors
   that can be quite difficult to debug. Be sure to declare your
   `upstreams` equivalent in a way that won't do load-balancing
   unexpectedly (e.g., pointing to a DNS name that you haven't configured
   with multiple IPs for your Zulip machine; sometimes this happens with
   IPv6 configuration).

[no-proto-header]: system-configuration.md#rejects_http_requests
[nginx-proxy-longpolling-config]: https://github.com/zulip/zulip/blob/main/puppet/zulip/files/nginx/zulip-include-common/proxy_longpolling
