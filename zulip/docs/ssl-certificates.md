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
wget https://dl.eff.org/certbot-auto
chmod a+x certbot-auto
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
