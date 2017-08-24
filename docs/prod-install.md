# Production Installation

Make sure you want to install a Zulip production server. If you'd
instead like to test or develop a new feature, we recommend the
[Zulip server development environment](dev-overview.html#requirements) instead.

You will need an Ubuntu system that satisfies
[the installation requirements](prod-requirements.html).  In short,
you need:
* Either a dedicated machine, or a fresh VM on an existing machine.
* Ubuntu 14.04 Trusty or Ubuntu 16.04 Xenial, 64-bit.
* At least 2GB RAM and 10 GB disk space (4GB and 2 CPUs recommended for 100+ users).
* A DNS name, an SSL certificate, and credentials for sending email.

## Step 1: Install SSL Certificates

Zulip runs over `https` only, and requires SSL certificates in order to
work. It looks for the certificates in `/etc/ssl/private/zulip.key`
and `/etc/ssl/certs/zulip.combined-chain.crt`.  Note that Zulip uses
`nginx` as its webserver and thus [expects a chained certificate
bundle](http://nginx.org/en/docs/http/configuring_https_servers.html).

If you need an SSL certificate, see [our SSL certificate
documentation](ssl-certificates.html).  If you already have an SSL
certificate, just install (or symlink) it into place at the above
paths, and move on to the next step.

## Step 2: Download and install latest release

If you haven't already, download and unpack [the latest built server
tarball](https://www.zulip.org/dist/releases/zulip-server-latest.tar.gz)
with the following commands:

```
cd $(mktemp -d)
wget https://www.zulip.org/dist/releases/zulip-server-latest.tar.gz
tar -xf zulip-server-latest.tar.gz
```

Then, run the Zulip install script:
```
sudo -s  # If not already root
./zulip-server-*/scripts/setup/install
```

This may take a while to run, since it will install a large number of
dependencies.

The Zulip install script is designed to be idempotent, so if it fails,
you can just rerun it after correcting the issue that caused it to
fail.  Also note that it automatically logs a transcript to
`/var/log/zulip/install.log`; please include a copy of that file in
any bug reports.

The install script does several things:
* Creates `zulip` user, which the various Zulip servers will run as,
* Creates `/home/zulip/deployments/`, which the Zulip code for this
deployment (and future deployments when you upgrade) go into.  At the
very end of the install process, the script moves the Zulip code tree
it's running from (which you unpacked from a tarball above) to a
directory there, and makes `/home/zulip/deployments/current` as a
symbolic link to it.
* Installs Zulip's various dependencies.
* Cconfigures the various third-party services Zulip uses, including
Postgres, RabbitMQ, Memcached and Redis.

## Step 3: Configure Zulip

Configure the Zulip server instance by editing `/etc/zulip/settings.py` and
providing values for the mandatory settings, which are all found under the
heading `### MANDATORY SETTINGS`.  These settings include:

- `EXTERNAL_HOST`: the user-accessible Zulip domain name for your
  Zulip installation (i.e., what users will type in their web
  browser). This should of course match the DNS name you configured to
  point to your server and for which you configured SSL certificates.
  If you plan to use multiple domains, add the others to
  `ALLOWED_HOSTS`.

- `ZULIP_ADMINISTRATOR`: the email address of the person or team
  maintaining this installation and who will get support and error
  emails.

- `EMAIL_HOST`, `EMAIL_HOST_USER`: credentials for an outgoing email
  (aka "SMTP") server that Zulip can use to send emails.  See
  [our guide for outgoing email](prod-email.html) for help configuring
  this.

- If desired, you can also configure additional
  [authentication backends](prod-authentication-methods.html) while
  you're editing /etc/zulip/settings.py.  Note, however, that the
  default (email) backend must be enabled when you complete Step 6
  (creating an organization) below.

## Step 4: Test email configuration

If you haven't already,
[test your outgoing email configuration](prod-email.html#testing-and-troubleshooting).
This is important to test now, because email configuration errors are
common, and your outgoing email configuration needs to be working in
order for you to complete the installation.

## Step 5: Initialize Zulip database

At this point, you are done doing things as root. The remaining
commands are run as the `zulip` user using `su zulip`. To initialize
the Zulip database for your production install, run:

```
su zulip -c /home/zulip/deployments/current/scripts/setup/initialize-database
```

The `initialize-database` script will report an error if you did not
fill in all the mandatory settings from `/etc/zulip/settings.py`.  It
is safe to rerun it after correcting the problem if that happens.

This completes the process of installing Zulip on your server.
However, in order to use Zulip, you'll need to create an organization
in your Zulip installation.

## Step 6: Create a Zulip organization and login

* Run the organization (realm) creation [management
command](prod-maintain-secure-upgrade.html#management-commands) :

  ```
  su zulip # If you weren't already the zulip user
  /home/zulip/deployments/current/manage.py generate_realm_creation_link
  ```

  This will print out a secure one-time-use link that allows creation of a
  new Zulip organization on your server.

* Open the generated link with your web browser. You'll see the "Create
organization" page ([screenshot here](_static/zulip-create-realm.png)).
Enter your email address and click *Create organization*.

* Check your email to find the confirmation email and click the
link. You'll be prompted to finish setting up your organization and
initial administrator user ([screenshot
here](_static/zulip-create-user-and-org.png)).  Complete this form and
log in!

**Congratulations!** You are logged in as an organization
administrator for your new Zulip organization.

## Step 7: Next steps

* Subscribe to the extremely low-traffic
[Zulip announcements email list](https://groups.google.com/forum/#!forum/zulip-announce)
to get important announcements for Zulip server administrators about
new releases, security issues, etc.
* [Follow Zulip on Twitter](https://twitter.com/zulip) to get Zulip news.
* [Learn how to setup your new Zulip organization][realm-admin-docs].
* [Learn how further configure your Zulip server](prod-customize.html).
* [Learn about maintaining a production Zulip server](prod-maintain-secure-upgrade.html).

## Troubleshooting

If you get an error after `scripts/setup/install` completes, check the
bottom of `/var/log/zulip/errors.log` for a traceback, and consult the
[troubleshooting section](prod-troubleshooting.html) for advice on how
to debug.

If that doesn't help, please visit
[#production help](https://chat.zulip.org/#narrow/stream/production.20help)
in the [Zulip development community server](chat-zulip-org.html) for
realtime help or email zulip-help@googlegroups.com with the full
traceback, and we'll try to help you out!  Please provide details like
the full traceback from the bottom of `/var/log/zulip/errors.log` in
your report.

[realm-admin-docs]: https://zulipchat.com/help/getting-your-organization-started-with-zulip
