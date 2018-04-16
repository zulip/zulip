# Installing SSL Certificates

To keep your communications secure, Zulip runs over HTTPS only.
You'll need an SSL/TLS certificate.

Fortunately, since about 2017, new options can make getting and
maintaining a genuine, trusted-by-browsers certificate no longer the
chore (nor expense) that it used to be.

## Manual install

If you already have an SSL certificate, just install (or symlink) its
files into place at the following paths:
* `/etc/ssl/private/zulip.key` for the private key
* `/etc/ssl/certs/zulip.combined-chain.crt` for the certificate.

Your certificate file should contain not only your own certificate but
its full chain, including any intermediate certificates used by your
CA.  See the [nginx documentation][nginx-chains] for details on what
this means and how to do it and test it.  If you're missing part of
the chain, your server may work with some browsers but not others.

[nginx-chains]: http://nginx.org/en/docs/http/configuring_https_servers.html#chains

## Certbot (recommended)

[Let's Encrypt](https://letsencrypt.org/) is a free, completely
automated CA launched in 2016 to help make HTTPS routine for the
entire Web.  Zulip offers a simple automation for
[Certbot](https://certbot.eff.org/), a Let's Encrypt client, to get
SSL certificates from Let's Encrypt and renew them automatically.

We recommend most Zulip servers use Certbot.  You'll want something
else if:
* you have an existing workflow for managing SSL certificates
  that you prefer;
* you need wildcard certificates (support from Let's Encrypt planned
  for [early 2018][letsencrypt-wildcard]); or
* your Zulip server is not on the public Internet. (In this case you
  can [still use Certbot][certbot-manual-mode], but it's less
  convenient; and you'll want to ignore Zulip's automation.)

[letsencrypt-wildcard]: https://letsencrypt.org/2017/07/06/wildcard-certificates-coming-jan-2018.html
[certbot-manual-mode]: https://certbot.eff.org/docs/using.html#manual

### At initial Zulip install

To enable the Certbot automation when first installing Zulip, just
pass the `--certbot` flag when [running the install script][doc-install-script].

The `--hostname` and `--email` options are required when using
`--certbot`.  You'll need the hostname to be a real DNS name, and the
Zulip server machine to be reachable by that name from the public
Internet.

[doc-install-script]: ../production/install.html#step-2-install-zulip

### After Zulip is already installed

To enable the Certbot automation on an already-installed Zulip
server, run the following commands:
```
sudo -s  # If not already root
/home/zulip/deployments/current/scripts/setup/setup-certbot --hostname=HOSTNAME --email=EMAIL
```
where HOSTNAME is the domain name users see in their browser when
using the server (e.g., `zulip.example.com`), and EMAIL is a contact
address for the server admins.

### How it works

When the Certbot automation in Zulip is first enabled, by either
method, it creates an account for the server at the Let's Encrypt CA;
requests a certificate for the given hostname; proves to the CA that
the server controls the website at that hostname; and is then given a
certificate.  (For details, refer to
[Let's Encrypt](https://letsencrypt.org/how-it-works/).)

Then it records a flag in `/etc/zulip/zulip.conf` saying Certbot is in
use and should be auto-renewed.  A cron job checks that flag, then
checks if any certificates are due for renewal, and if they are (so
approximately once every 60 days), repeats the process of request,
prove, get a fresh certificate.


## Self-signed certificate

If you aren't able to use Certbot, you can generate a
self-signed SSL certificate.  This isn't suitable for production use
(because it's insecure, and because browsers and the Zulip apps will
complain that it's insecure), but may be convenient for testing.

To generate a self-signed certificate when first installing Zulip,
just pass the `--self-signed-cert` flag when
[running the install script][doc-install-script].

To generate a self-signed certificate for an already-installed Zulip
server, run the following commands:
```
sudo -s  # If not already root
/home/zulip/deployments/current/scripts/setup/generate-self-signed-cert HOSTNAME
```
where HOSTNAME is the domain name (or IP address) to use on the
generated certificate.
