# Production Installation

Make sure you want to install a Zulip production server. If you'd
instead like to test or develop a new feature, we recommend the
[Zulip server development environment](../development/overview.html#requirements) instead.

You will need an Ubuntu system that satisfies
[the installation requirements](../production/requirements.html).  In short,
you need:
* A dedicated machine or VM.
* A supported OS:
  * Ubuntu 16.04 Xenial 64-bit
  * Ubuntu 14.04 Trusty 64-bit (not recommended for new installations)
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

This takes a few minutes to run, as it installs Zulip's dependencies.
For more on what the installer does, [see details below](#installer-details).

If the script gives an error, consult [Troubleshooting](#troubleshooting) below.

#### Installer options

* `--email=you@example.com`: The email address of the person or team
  who should get support and error emails from this Zulip server.
  This becomes `ZULIP_ADMINISTRATOR` ([docs][doc-settings]) in the
  Zulip settings.

* `--hostname=zulip.example.com`: The user-accessible domain name for
  this Zulip server, i.e., what users will type in their web browser.
  This becomes `EXTERNAL_HOST` ([docs][doc-settings]) in the Zulip
  settings.

* `--self-signed-cert`: With this option, the Zulip installer
  generates a self-signed SSL certificate for the server.  This isn't
  suitable for production use, but may be convenient for testing.

* `--certbot`: With this option, the Zulip installer automatically
  obtains an SSL certificate for the server [using Certbot][doc-certbot].
  If you'd prefer to acquire an SSL certificate yourself in any other
  way, it's easy to [provide it to Zulip][doc-ssl-manual].

[doc-settings]: ../production/settings.html
[doc-certbot]: ../production/ssl-certificates.html#certbot-recommended
[doc-ssl-manual]: ../production/ssl-certificates.html#manual-install

## Step 3: Create a Zulip organization and log in

When the install script successfully completes, it prints a secure
one-time-use link that allows creation of a new Zulip organization on
your server.

Open that link with your web browser. You'll see the "Create
organization" page ([screenshot here](../_static/zulip-create-realm.png)).
Enter your email address and click *Create organization*.

You'll be prompted to finish setting up your organization, and your
own user account as the initial administrator of the organization
([screenshot here](../_static/zulip-create-user-and-org.png)).
Complete this form and log in!

**Congratulations!** You are logged in as an organization
administrator for your new Zulip organization.

## Step 4: Configure outgoing email

Zulip needs to be able to send email in order to confirm new users'
email addresses, and to send email notifications.  You'll need to
provide Zulip with credentials on an email server it can use for
outgoing messages.

See [our guide for outgoing email](email.html) for detailed
instructions, including references to free outgoing-email services if
you don't have one already.  You'll set the host and username in
`/etc/zulip/settings.py` and the password in
`/etc/zulip/zulip-secrets.conf`, then restart Zulip to pick up the new
configuration.

When you're done, [be sure to
test](email.html#testing-and-troubleshooting) your new email
configuration.

## Step 5: Next steps

* Subscribe to the extremely low-traffic
[Zulip announcements email list](https://groups.google.com/forum/#!forum/zulip-announce)
to get important announcements for Zulip server administrators about
new releases, security issues, etc.
* [Follow Zulip on Twitter](https://twitter.com/zulip) to get Zulip news.
* [Learn how to setup your new Zulip organization][realm-admin-docs].
* [Learn how configure your Zulip server settings](settings.html).
* [Learn about maintaining a production Zulip server](../production/maintain-secure-upgrade.html).

[realm-admin-docs]: https://zulipchat.com/help/getting-your-organization-started-with-zulip

```eval_rst
.. _installer-details:
```
## Details: What the installer does

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
* Initializes Zulip's database.

## Troubleshooting

**Install script.**
The Zulip install script is designed to be idempotent.  This means
that if it fails, then once you've corrected the cause of the failure,
you can just rerun the script.

The install script automatically logs a transcript to
`/var/log/zulip/install.log`.  In case of failure, you might find the
log handy for resolving the issue.  Please include a copy of this log
file in any bug reports.

**The `zulip` user's password.**
By default, the `zulip` user doesn't
have a password, and is intended to be accessed by `su zulip` from the
`root` user (or via SSH keys or a password, if you want to set those
up, but that's up to you as the system administrator).  Most people
who are prompted for a password when running `su zulip` turn out to
already have switched to the `zulip` user earlier in their session,
and can just skip that step.

**After the install script.**
If you get an error after `scripts/setup/install` completes, check
the bottom of `/var/log/zulip/errors.log` for a traceback, and consult
the [troubleshooting section](troubleshooting.html) for advice on
how to debug.

**Community.**
If the tips above don't help, please visit
[#production help](https://chat.zulip.org/#narrow/stream/production.20help)
in the [Zulip development community server](../contributing/chat-zulip-org.html) for
realtime help or email zulip-help@googlegroups.com with the full
traceback, and we'll try to help you out!  Please provide details like
the full traceback from the bottom of `/var/log/zulip/errors.log` in
your report.
