# Installing SSL Certificates

To keep your communications secure, Zulip runs over HTTPS only.
You'll need an SSL/TLS certificate.

Fortunately, as of 2017 new options can make getting and maintaining a
genuine, trusted-by-browsers certificate no longer the chore (nor
expense) that it used to be.

## Manual install

If you already have an SSL certificate, just install (or symlink) its
files into place at the following paths:
* `/etc/ssl/private/zulip.key` for the private key
* `/etc/ssl/certs/zulip.combined-chain.crt` for the certificate.
  Because Zulip uses nginx as its web server, this should be in the
  format of a [chained certificate bundle][nginx-https].

[nginx-https]: http://nginx.org/en/docs/http/configuring_https_servers.html

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
  for [January 2018][letsencrypt-wildcard]); or
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

If you aren't able to use Let's Encrypt, you can generate a
self-signed ssl certificate.  We recommend getting a real certificate
using Let's Encrypt over this approach because browsers (and the the
Zulip apps) will complain when connecting to your server that the
certificate isn't signed (for good reason: self-signed certificates
are a security risk!).

Run all the commands in this section as root. If you're not already
logged in as root, use `sudo -i` to start an interactive root shell.

The quickest way to create a cert is to use the script we provide:

```
scripts/setup/generate-self-signed-certs zulip.example.com
```

from the root of your Zulip directory (replacing `zulip.example.com`
with the hostname of your server i.e. whatever you're going to set as
`EXTERNAL_HOST`).

### Generating a self-signed cert manually

We also document the steps below if you want to create a cert
manually, which will offer you an opportunity to set your organization
name (etc.).

```
apt-get install openssl
openssl genrsa -des3 -passout pass:x -out server.pass.key 4096
openssl rsa -passin pass:x -in server.pass.key -out zulip.key
rm server.pass.key
openssl req -new -key zulip.key -out server.csr

# The last step above will ask some questions interactively.
# Run these after answering the questions about your cert.
openssl x509 -req -days 365 -in server.csr -signkey zulip.key -out zulip.combined-chain.crt
rm server.csr
cp zulip.key /etc/ssl/private/zulip.key
cp zulip.combined-chain.crt /etc/ssl/certs/zulip.combined-chain.crt
```

You will eventually want to get a properly signed SSL certificate, but
this will let you finish the installation process.

### If you are using a self-signed certificate with an IP address (no domain)

Finally, if you want to proceed with just an IP address, it is
possible to finish a Zulip installation that way; just set
`EXTERNAL_HOST` to be the IP address.
