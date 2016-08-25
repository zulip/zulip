# Install in Production

Ensure you have an Ubuntu system that satisfies [the installation
requirements](prod-requirements.html).

Prior to installing Zulip, you should have an Ubuntu 14.04 Trusty
64-bit server instance, with at least 4GB RAM, 2 CPUs, and 10 GB disk
space. You should also have a domain name available and have updated
its DNS record to point to the server.

## Step 1: Install SSL Certificates

Zulip runs over https only and requires ssl certificates in order to
work. It looks for the certificates in `/etc/ssl/private/zulip.key`
and `/etc/ssl/certs/zulip.combined-chain.crt`.  Note that Zulip uses
`nginx` as its webserver and thus [expects a chained certificate
bundle](http://nginx.org/en/docs/http/configuring_https_servers.html)

If you already have an SSL certificate, just install (or symlink) them
into place at the above paths, and move on to the next step.

### Using Let's Encrypt

If you have a domain name and you've configured DNS to point to the
server where you want to install Zulip, you can use [Let's
Encrypt](https://letsencrypt.org/) to generate a valid, properly
signed SSL certificates, for free.

Run all of these commands as root. If you're not already logged in as root, use
`sudo -i` to start an interactive root shell.

First, install the Let's Encrypt client [Certbot](https://certbot.eff.org/) and
then generate the certificate:

```
apt-get install -y git bc openssl
git clone https://github.com/certbot/certbot /opt/letsencrypt
cd /opt/letsencrypt
./certbot-auto certonly --standalone
```

Note: If you already had a webserver installed on this system (e.g. you
previously installed Zulip and are now getting a cert), you will
need to stop the webserver (e.g. `service nginx stop`) and start it
again after (e.g. `service nginx start`) running the certbot command above.

Next, symlink the certificates to make them available where Zulip expects them.
Be sure to replace YOUR_DOMAIN with your domain name.

```
ln -s /etc/letsencrypt/live/YOUR_DOMAIN/privkey.pem /etc/ssl/private/zulip.key
ln -s /etc/letsencrypt/live/YOUR_DOMAIN/fullchain.pem /etc/ssl/certs/zulip.combined-chain.crt
```

Note: Certificates provided by Let's Encrypt are valid for 90 days and then
need to be [renewed](https://certbot.eff.org/docs/using.html#renewal). You can
renew with this command:

```
./certbot-auto renew
```

### Generating a self-signed certificate

If you aren't able to use Let's Encrypt, you can generate a
self-signed ssl certificate.  We recommend getting a real certificate
using LetsEncrypt over this approach because your browser (and some of
the Zulip clients) will complain when connecting to your server that
the certificate isn't signed.

Run all of these commands as root. If you're not already logged in as root, use
`sudo -i` to start an interactive root shell.

```
apt-get install openssl
openssl genrsa -des3 -passout pass:x -out server.pass.key 4096
openssl rsa -passin pass:x -in server.pass.key -out zulip.key
rm server.pass.key
openssl req -new -key zulip.key -out server.csr
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
EXTERNAL_HOST to be the IP address.

## Step 2: Download and unpack latest release

Download [the latest built server
tarball](https://www.zulip.com/dist/releases/zulip-server-latest.tar.gz) and
unpack it to `/root/zulip`.

Run all of these commands as root. If you're not already logged in as root, use
`sudo -i` to start an interactive root shell.

```
wget https://www.zulip.com/dist/releases/zulip-server-latest.tar.gz
mkdir -p /root/zulip && tar -xf zulip-server-latest.tar.gz --directory=/root/zulip --strip-components=1
```

## Step 3: Run install script

Run all of these commands as root. If you're not already logged in as root, use
`sudo -i` to start an interactive root shell.

```
/root/zulip/scripts/setup/install
```

This may take a while to run, since it will install a large number of
packages via apt.

The Zulip install script is designed to be idempotent, so if it fails,
you can just rerun it after correcting the issue that caused it to
fail.  Also note that it automatically logs a transcript to
`/var/log/zulip/install.log`; please include a copy of that file in
any bug reports.

## Step 4: Configure Zulip

Configure the Zulip server instance by editing `/etc/zulip/settings.py` and
providing values for the mandatory settings, which are all found under the
heading `### MANDATORY SETTINGS`.

These settings include:

- `EXTERNAL_HOST`: the user-accessible Zulip domain name for your Zulip
  installation. This will be the domain for which you have DNS A records
  pointing to this server and for which you configured SSL certificates.

- `ZULIP_ADMINISTRATOR`: the email address of the person or team maintaining
  this installation and who will get support emails.

- `ADMIN_DOMAIN`: the domain for your organization. Usually this is the main
  domain used in your organization's email addresses.

- `AUTHENTICATION_BACKENDS`: a list of enabled authentication
  mechanisms.  You'll need to enable at least one authentication
  mechanism by uncommenting its corresponding line, and then also do
  any additional configuration required for that backend as documented
  in the `settings.py` file.  See the [section on
  Authentication](prod-auth-first-login.html) for more detail on the
  available authentication backends and how to configure them.

- `EMAIL_*`, `DEFAULT_FROM_EMAIL`, and `NOREPLY_EMAIL_ADDRESS`:
  Regardless of which authentication backends you enable, you must
  provide settings for an outgoing SMTP server so Zulip can send
  emails when needed.  We highly recommend testing your configuration
  using `manage.py send_test_email` to confirm your outgoing email
  configuration is working correctly.

- `ALLOWED_HOSTS`: Replace `*` with the fully qualified DNS name for
  your Zulip server here.

## Step 5: Run database initialization

To initialize the Zulip database for your production install, run:

```
su zulip -c /home/zulip/deployments/current/scripts/setup/initialize-database
```

Note the use of `su zulip`. The `initialize-database` command and others like
it need to be run by the `zulip` user.  You can do this by running each command
with `su zulip -c` or by starting an interactive shell as the zulip user with
`sudo -u zulip -i`.

The `initialize-database` script will report an error if you did not
fill in all the mandatory settings from `/etc/zulip/settings.py`.  It
is safe to rerun it after correcting the problem if that happens.

Once this script completes successfully, the main installation process will be
complete, and zulip services will be running.

## Step 6: Subscribe

Subscribe to low-traffic [the Zulip announcements Google
Group](https://groups.google.com/forum/#!forum/zulip-announce) to get
announcements about new releases, security issues, etc.

Congratulations! Next: [Logging in and creating users](prod-auth-first-login.html).
