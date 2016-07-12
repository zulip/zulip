Installing Zulip in production
==============================

Ensure you have an Ubuntu system that satisfies [the installation
requirements](prod-requirements.html).

These instructions should be followed as root.

(1) Install the SSL certificates for your machine to
  `/etc/ssl/private/zulip.key` and `/etc/ssl/certs/zulip.combined-chain.crt`.

  If you don't know how to generate an SSL certificate, you can
  do the following to generate a self-signed certificate:

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
  installation process.  When you do get an actual certificate, you
  will need to install as /etc/ssl/certs/zulip.combined-chain.crt the
  full certificate authority chain, not just the certificate; see the
  section on "SSL certificate chains" [in the nginx
  docs](http://nginx.org/en/docs/http/configuring_https_servers.html)
  for how to do this:

  You can get a free, properly signed certificate from the [Let's
  Encrypt service](https://letsencrypt.org/); here are the simplified
  instructions for using it with Zulip (run it all as root):

  ```
  sudo apt-get install -y git bc openssl
  git clone https://github.com/letsencrypt/letsencrypt /opt/letsencrypt
  cd /opt/letsencrypt
  letsencrypt-auto certonly --standalone

  # Now symlink the certificates to make them available where Zulip expects them.
  ln -s /etc/letsencrypt/live/your_domain/privkey.pem /etc/ssl/private/zulip.key
  ln -s /etc/letsencrypt/live/your_domain/fullchain.pem /etc/ssl/certs/zulip.combined-chain.crt
  ```

  If you already had a webserver installed on the system (e.g. you
  previously installed Zulip and are now getting a cert), you will
  need to stop the webserver (e.g. `service nginx stop`) and start it
  again after (e.g. `service nginx start`) running the above.

  Finally, if you want to proceed with just an IP address, it is
  possible to finish a Zulip installation that way; just set
  EXTERNAL_HOST to be the IP address.

(2) Download [the latest built server tarball](https://www.zulip.com/dist/releases/zulip-server-latest.tar.gz)
  and unpack it to `/root/zulip`, e.g.
  ```
  wget https://www.zulip.com/dist/releases/zulip-server-latest.tar.gz
  mkdir -p /root/zulip && tar -xf zulip-server-latest.tar.gz --directory=/root/zulip --strip-components=1
  ```

(3) Run
  ```
  /root/zulip/scripts/setup/install
  ```
  This may take a while to run, since it will install a large number of
  packages via apt.

(4) Configure the Zulip server instance by filling in the settings in
  `/etc/zulip/settings.py`.  Be sure to fill in all the mandatory
  settings, enable at least one authentication mechanism, and do the
  configuration required for that authentication mechanism to work.
  See the section on "Authentication" below for more detail on
  configuring authentication mechanisms.

(5) Run
  ```
  su zulip -c /home/zulip/deployments/current/scripts/setup/initialize-database
  ```
  This will report an error if you did not fill in all the mandatory
  settings from `/etc/zulip/settings.py`.  Once this completes
  successfully, the main installation process will be complete, and if
  you are planning on using password authentication, you should be able
  to visit the URL for your server and register for an account.

(6) Subscribe to [the Zulip announcements Google Group](https://groups.google.com/forum/#!forum/zulip-announce)
  to get announcements about new releases, security issues, etc.

Congratulations! Next: [Authentication and logging into Zulip the first time](https://github.com/zulip/zulip/blob/master/README.prod.md#authentication-and-logging-into-zulip-the-first-time).
