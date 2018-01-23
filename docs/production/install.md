# Production Installation

Make sure you want to install a Zulip production server. If you'd
instead like to test or develop a new feature, we recommend the
[Zulip server development environment](../development/overview.html#requirements) instead.

You will need an Ubuntu system that satisfies
[the installation requirements](../production/requirements.html).  In short,
you need:
* Either a dedicated machine, or a fresh VM on an existing machine.
* Ubuntu 16.04 Xenial or Ubuntu 14.04 Trusty, 64-bit.  If you have a
  choice, install on Xenial, since Trusty is approaching its
  end-of-life and you'll save yourself the work of upgrading a
  production installation.
* At least 2GB RAM and 10 GB disk space (4GB and 2 CPUs recommended for 100+ users).
* A DNS name, an SSL certificate, and credentials for sending email.
  For most users, you can just use our handy `--certbot` option to
  generate the SSL certificate.

## Step 1: Download the latest release

Download and unpack [the latest built server
tarball](https://www.zulip.org/dist/releases/zulip-server-latest.tar.gz)
with the following commands:

```
cd $(mktemp -d)
wget https://www.zulip.org/dist/releases/zulip-server-latest.tar.gz
tar -xf zulip-server-latest.tar.gz
```

If you'd like to verify the download, we
[publish the sha256sums of our release tarballs](https://www.zulip.org/dist/releases/SHA256SUMS.txt).

## Step 2: Install Zulip

```eval_rst
.. only:: unreleased

   .. warning::
      You are reading a **development version** of the Zulip documentation.
      These instructions may not correspond to the latest Zulip Server
      release.  See `documentation for the latest release`__.

__ https://zulip.readthedocs.io/en/stable/prod-install.html
```

To set up Zulip with the most common configuration, you can run the
installer as follows:

```
sudo -i  # If not already root
./zulip-server-*/scripts/setup/install --certbot \
    --email=YOUR_EMAIL --hostname=YOUR_HOSTNAME
```

This will take a while to run, since it will install a large number of
dependencies from the PyPI and NPM repositories.

#### Installer options

* `--email=you@example.com`: The email address of the person or team
  who should get support and error emails from this Zulip server.
  This becomes `ZULIP_ADMINISTRATOR` ([docs][doc-settings]) in the
  Zulip settings.

* `--hostname=zulip.example.com`: The user-accessible domain name for
  this Zulip server, i.e., what users will type in their web browser.
  This becomes `EXTERNAL_HOST` ([docs][doc-settings]) in the Zulip
  settings.

* `--certbot`: With this option, the Zulip installer automatically
  obtains an SSL certificate for the server [using Certbot][doc-certbot].
  If you'd prefer to acquire an SSL certificate yourself in any other
  way, it's easy to [provide it to Zulip][doc-ssl-manual].

[doc-settings]: ../production/customize.html
[doc-certbot]: ../production/ssl-certificates.html#certbot-recommended
[doc-ssl-manual]: ../production/ssl-certificates.html#manual-install

#### What the installer does

The install script does several things:
* Creates the `zulip` user, which the various Zulip servers will run as.
* Creates `/home/zulip/deployments/`, which the Zulip code for this
deployment (and future deployments when you upgrade) goes into.  At the
very end of the install process, the script moves the Zulip code tree
it's running from (which you unpacked from a tarball above) to a
directory there, and makes `/home/zulip/deployments/current` as a
symbolic link to it.
* Installs Zulip's various dependencies.
* Configures the various third-party services Zulip uses, including
Postgres, RabbitMQ, Memcached and Redis.

#### Troubleshooting install failures

The Zulip install script is designed to be idempotent.  This means
that if it fails, then once you've corrected the cause of the failure,
you can just rerun the script.

The install script automatically logs a transcript to
`/var/log/zulip/install.log`.  In case of failure, you might find the
log handy for resolving the issue.  Please include a copy of this log
file in any bug reports.

## Step 3: Configure outgoing email

Configure the Zulip server instance by editing
`/etc/zulip/settings.py` to enable your server's ability to send
outgoing emails:

- `EMAIL_HOST`, `EMAIL_HOST_USER`: credentials for an outgoing email
  (aka "SMTP") server that Zulip can use to send emails.  See
  [our guide for outgoing email](email.html) for help configuring
  this.

## Step 4: Test email configuration

[Test your outgoing email configuration](email.html#testing-and-troubleshooting).
This is important to test now, because email configuration errors are
common, and your outgoing email configuration needs to be working in
order for you to complete the installation.

## Step 5: Initialize Zulip database

At this point, you are done doing things as root. The remaining
commands are run as the `zulip` user. Change to the `zulip` user
and initialize the Zulip database for your production install:

```
su zulip # If you weren't already the zulip user
/home/zulip/deployments/current/scripts/setup/initialize-database
```

The `initialize-database` script will report an error if you did not
fill in all the mandatory settings from `/etc/zulip/settings.py`.  It
is safe to rerun it after correcting the problem if that happens.

This completes the process of installing Zulip on your server.
However, in order to use Zulip, you'll need to create an organization
in your Zulip installation.

## Step 6: Create a Zulip organization and login

* Run the organization (realm) creation [management
command](../production/maintain-secure-upgrade.html#management-commands) :

  ```
  su zulip # If you weren't already the zulip user
  /home/zulip/deployments/current/manage.py generate_realm_creation_link
  ```

  This will print out a secure one-time-use link that allows creation of a
  new Zulip organization on your server.

* Open the generated link with your web browser. You'll see the "Create
organization" page ([screenshot here](../_static/zulip-create-realm.png)).
Enter your email address and click *Create organization*.

* Check your email to find the confirmation email and click the
link. You'll be prompted to finish setting up your organization and
initial administrator user ([screenshot
here](../_static/zulip-create-user-and-org.png)).  Complete this form and
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
* [Learn how further configure your Zulip server](customize.html).
* [Learn about maintaining a production Zulip server](../production/maintain-secure-upgrade.html).

## Troubleshooting

* The `zulip` user's password.  By default, the `zulip` user doesn't
have a password, and is intended to be accessed by `su zulip` from the
`root` user (or via SSH keys or a password, if you want to set those
up, but that's up to you as the system administrator).  Most people
who are prompted for a password when running `su zulip` turn out to
already have switched to the `zulip` user earlier in their session,
and can just skip that step.

* If you get an error after `scripts/setup/install` completes, check
the bottom of `/var/log/zulip/errors.log` for a traceback, and consult
the [troubleshooting section](troubleshooting.html) for advice on
how to debug.

* If that doesn't help, please visit
[#production help](https://chat.zulip.org/#narrow/stream/production.20help)
in the [Zulip development community server](../contributing/chat-zulip-org.html) for
realtime help or email zulip-help@googlegroups.com with the full
traceback, and we'll try to help you out!  Please provide details like
the full traceback from the bottom of `/var/log/zulip/errors.log` in
your report.

[realm-admin-docs]: https://zulipchat.com/help/getting-your-organization-started-with-zulip
