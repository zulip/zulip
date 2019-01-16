# Production Installation

Make sure you want to install a Zulip production server. If you'd
instead like to test or develop a new feature, we recommend the
[Zulip development server](../development/overview.html#requirements) instead.
If you just want to play around with Zulip and see what it looks like, you
can create a test organization at <https://zulipchat.com>.

You'll need an Ubuntu or Debian system that satisfies
[the installation requirements](../production/requirements.html), or
you can use Zulip's [experimental Docker image](../production/deployment.html#zulip-in-docker).

## Step 1: Download the latest release

Download and unpack [the latest built server
tarball](https://www.zulip.org/dist/releases/zulip-server-latest.tar.gz)
with the following commands:

```
cd $(mktemp -d)
wget https://www.zulip.org/dist/releases/zulip-server-latest.tar.gz
tar -xf zulip-server-latest.tar.gz
```

* If you'd like to verify the download, we
[publish the sha256sums of our release tarballs](https://www.zulip.org/dist/releases/SHA256SUMS.txt).
* You can also
[install a pre-release version of Zulip](../production/deployment.html#installing-zulip-from-git)
using code from our [repository on GitHub](https://github.com/zulip/zulip/).

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
sudo -s  # If not already root
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

## Step 3: Create a Zulip organization, and log in

On success, the install script prints a link.  If you're [restoring a
backup][zulip-backups] or importing your data from [HipChat][hipchat-import],
[Slack][slack-import], or another Zulip server, you should stop here
and return to the the import instructions.

[hipchat-import]: https://zulipchat.com/help/import-from-hipchat
[slack-import]: https://zulipchat.com/help/import-from-slack
[zulip-backups]: ../production/maintain-secure-upgrade.html#backups

Otherwise, open the link in a browser.  Follow the prompts to set up
your organization, and your own user account as an administrator.
Then, log in!

The link is a secure one-time-use link.  If you need another
later, you can generate a new one by running `manage.py
generate_realm_creation_link` on the server.  See also our doc on
running [multiple organizations on the same server](multiple-organizations.html)
if that's what you're planning to do.

## Step 4: Configure and use

To really see Zulip in action, you'll need to get the people you work
together with using it with you.
* [Set up outgoing email](email.html) so Zulip can confirm new users'
  email addresses and send notifications.
* Learn how to [get your organization started][realm-admin-docs] using
  Zulip at its best.

Learning more:

* Subscribe to the
[Zulip announcements email list](https://groups.google.com/forum/#!forum/zulip-announce)
for server administrators.  This extremely low-traffic list is for
important announcements, including new releases and security issues.
* Follow [Zulip on Twitter](https://twitter.com/zulip).
* Learn how to [configure your Zulip server settings](settings.html).
* Learn about [maintaining a production Zulip server](maintain-secure-upgrade.html).

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

If you'd like to deploy Zulip with these services on different
machines, check out our [deployment options documentation](deployment.html).

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
[#production help](https://chat.zulip.org/#narrow/stream/31-production-help)
in the [Zulip development community server](../contributing/chat-zulip-org.html) for
realtime help or email zulip-help@googlegroups.com with the full
traceback, and we'll try to help you out!  Please provide details like
the full traceback from the bottom of `/var/log/zulip/errors.log` in
your report.
