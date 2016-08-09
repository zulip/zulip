# Installing

Ensure you have an Ubuntu system that satisfies [the installation
requirements](prod-requirements.html).

Prior to installing Zulip, you should have an Ubuntu 14.04 Trusty 64-bit server instance, with at least 4GB RAM, 2 CPUs, and 10 GB disk space. You should also have a domain name available and have updated its A record to point to this server.

## Step 1: Install SSL Certificates

Zulip runs over https only and requires ssl certificates in order to work. It
looks for the certificates in `/etc/ssl/private/zulip.key` and
`/etc/ssl/certs/zulip.combined-chain.crt`.

### Using Let's Encrypt

If you have a full qualified domain name and its A record has been updated to
point to the server where you want to install Zulip, you can use [Let's
Encrypt](https://letsencrypt.org/) to generate a valid, properly signed SSL
certificates, for free.

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

### Using a self-signed certificate

If you aren't able to use Let's Encrypt, you can generate a self-signed ssl certificate.

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

You will eventually want to get a properly signed SSL certificate
(and note that at present the Zulip desktop app doesn't support
self-signed certificates), but this will let you finish the
installation process. When you do get an actual certificate, you
will need to install as /etc/ssl/certs/zulip.combined-chain.crt the
full certificate authority chain, not just the certificate; see the
section on "SSL certificate chains" [in the nginx
docs](http://nginx.org/en/docs/http/configuring_https_servers.html)
for how to do this.

### If you are using a self-signed certificate with an IP address (no fqdn)

Finally, if you want to proceed with just an IP address, it is
possible to finish a Zulip installation that way; just set
EXTERNAL_HOST to be the IP address.

## Step 2: Download and uppack latest release

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

The Zulip install script is designed to be idempotent, so if it
fails, you can just rerun it after correcting the issue that caused
it to fail.

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
- `AUTHENTICATION_BACKENDS`: a list of enabled authentication mechanisms.
  You'll need to enable at least one authentication mechanism by uncommenting
  its corresponding line.

See the [section on Authentication](prod-auth-first-login.html)
for more detail on configuring authentication mechanisms.

## Step 5: Run database initialization

To initialize the Zulip database for your production install, run:

```
su zulip -c /home/zulip/deployments/current/scripts/setup/initialize-database
```

Note the use of `su zulip`. The `initialize-database` command and others like
it need to be run by the `zulip` user.  You can do this by running each command
with `su zulip -c` or by starting an interactive shell as the zulip user with
`sudo -u zulip -i`.

The `initialize-database` script will report an error if you did not fill in
all the mandatory settings from `/etc/zulip/settings.py`.

Once this script completes successfully, the main installation process will be
complete, and zulip services will be running.

## Step 6: Configure authentication

Depending which [authentication backend](prod-authentication-methods.html) you
would like to use, you will need to do some additional setup documented in the
`settings.py` template:

* For Google authentication, follow the configuration instructions around
  `GOOGLE_OAUTH2_CLIENT_ID` and `GOOGLE_CLIENT_ID`.

* For GitHub authentication, follow the instructions around
  `SOCIAL_AUTH_GITHUB_KEY`.

* For Email authentication, follow the configuration instructions for outgoing
  SMTP from Django.  You can use `./manage.py send_test_email
  username@example.com` to test whether you've successfully configured outgoing
  SMTP.

For a complete list of authentication backends supported, read [Authentication
Methods](prod-authentication-methods.html) and take a look at
`/etc/zulip/settings.py` for details about how to cofigure each.

Once you have configured authentication, you should be able to log in. Read
[Authentication and logging into Zulip the first
time](prod-auth-first-login.html) for details.

## Step 7: Subscribe

Subscribe to [the Zulip announcements Google
Group](https://groups.google.com/forum/#!forum/zulip-announce) to get
announcements about new releases, security issues, etc.

Congratulations! Next: [Authentication and logging into Zulip the first time](prod-auth-first-login.html).
