# Install a Zulip server

## Before you begin

To install a Zulip server, you'll need an Ubuntu or Debian system that satisfies
[the installation requirements](requirements.md). Alternatively,
you can use a preconfigured
[DigitalOcean droplet](https://marketplace.digitalocean.com/apps/zulip?refcode=3ee45da8ee26), or
Zulip's
[experimental Docker image](deployment.md#zulip-in-docker).

### Should I follow this installation guide?

- If you would like to try out Zulip, you can start by [checking it out in the
  Zulip development community](https://zulip.com/try-zulip), or [create a test
  Zulip Cloud organization](https://zulip.com/new).

- If you are deciding between self-hosting Zulip and signing up for [Zulip
  Cloud](https://zulip.com/plans/), our [self-hosting
  overview](https://zulip.com/self-hosting/) and [guide to choosing between
  Zulip Cloud and
  self-hosting](https://zulip.com/help/getting-your-organization-started-with-zulip#choosing-between-zulip-cloud-and-self-hosting)
  are great places to start.

- If you're developing for Zulip, you should follow the instructions
  to install Zulip's [development environment](../development/overview.md).

If you'd like to install a self-hosted Zulip server, this guide is for you!

## Step 1: Download the latest release

Download and unpack [the latest server
release](https://download.zulip.com/server/zulip-server-latest.tar.gz)
(**Zulip Server {{ LATEST_RELEASE_VERSION }}**) with the following commands:

```bash
cd $(mktemp -d)
curl -fLO https://download.zulip.com/server/zulip-server-latest.tar.gz
tar -xf zulip-server-latest.tar.gz
```

- If you'd like to verify the download, we
  [publish the sha256sums of our release tarballs](https://download.zulip.com/server/SHA256SUMS.txt).
- You can also
  [install a pre-release version of Zulip](deployment.md#installing-zulip-from-git)
  using code from our [repository on GitHub](https://github.com/zulip/zulip/).

## Step 2: Install Zulip

To set up Zulip with the most common configuration, you can run the
installer as follows:

```bash
sudo -s  # If not already root
./zulip-server-*/scripts/setup/install --certbot \
    --email=YOUR_EMAIL --hostname=YOUR_HOSTNAME
```

This takes a few minutes to run, as it installs Zulip's dependencies.
For more on what the installer does, [see details below](#details-what-the-installer-does).

If the script gives an error, consult [Troubleshooting](#troubleshooting) below.

#### Installer options

- `--email=you@example.com`: The email address for the person or team who
  maintains the Zulip installation. Note that this is a public-facing email
  address; it may appear on 404 pages, is used as the sender's address for many
  automated emails, and is advertised as a support address. An email address
  like support@example.com is totally reasonable, as is admin@example.com. Do
  not put a display name; e.g. "support@example.com", not "Zulip Support
  <support@example.com>". This becomes `ZULIP_ADMINISTRATOR`
  ([docs][doc-settings]) in the Zulip settings.

- `--hostname=zulip.example.com`: The user-accessible domain name for
  this Zulip server, i.e., what users will type in their web browser.
  This becomes `EXTERNAL_HOST` ([docs][doc-settings]) in the Zulip
  settings.

- `--self-signed-cert`: With this option, the Zulip installer
  generates a self-signed SSL certificate for the server. This isn't
  suitable for production use, but may be convenient for testing.

- `--certbot`: With this option, the Zulip installer automatically
  obtains an SSL certificate for the server [using
  Certbot][doc-certbot], and configures a cron job to renew the
  certificate automatically. If you'd prefer to acquire an SSL
  certificate yourself in any other way, it's easy to [provide it to
  Zulip][doc-ssl-manual].

You can see the more advanced installer options in our [deployment options][doc-deployment-options]
documentation.

[doc-settings]: settings.md
[doc-certbot]: ssl-certificates.md#certbot-recommended
[doc-ssl-manual]: ssl-certificates.md#manual-install
[doc-deployment-options]: deployment.md#advanced-installer-options

## Step 3: Create a Zulip organization, and log in

On success, the install script prints a link. If you're [restoring a
backup][zulip-backups] or importing your data from [Slack][slack-import],
or another Zulip server, you should stop here
and return to the import instructions.

[slack-import]: https://zulip.com/help/import-from-slack
[zulip-backups]: export-and-import.md#backups

Otherwise, open the link in a browser. Follow the prompts to set up
your organization, and your own user account as an administrator.
Then, log in!

The link is a secure one-time-use link. If you need another
later, you can generate a new one by running
`manage.py generate_realm_creation_link` on the server. See also our
doc on running [multiple organizations on the same
server](multiple-organizations.md) if that's what you're planning to
do.

## Step 4: Configure and use

To really see Zulip in action, you'll need to get the people you work
together with using it with you.

- [Set up outgoing email](email.md) so Zulip can confirm new users'
  email addresses and send notifications.
- Learn how to [get your organization started][realm-admin-docs] using
  Zulip at its best.

Learning more:

- Subscribe to the [Zulip announcements email
  list](https://groups.google.com/g/zulip-announce) for
  server administrators. This extremely low-traffic list is for
  important announcements, including [new
  releases](../overview/release-lifecycle.md) and security issues.
- Follow [Zulip on Twitter](https://twitter.com/zulip).
- Learn how to [configure your Zulip server settings](settings.md).
- Learn about [Backups, export and import](export-and-import.md)
  and [upgrading](upgrade.md) a production Zulip
  server.

[realm-admin-docs]: https://zulip.com/help/getting-your-organization-started-with-zulip

## Details: What the installer does

The install script does several things:

- Creates the `zulip` user, which the various Zulip servers will run as.
- Creates `/home/zulip/deployments/`, which the Zulip code for this
  deployment (and future deployments when you upgrade) goes into. At the
  very end of the install process, the script moves the Zulip code tree
  it's running from (which you unpacked from a tarball above) to a
  directory there, and makes `/home/zulip/deployments/current` as a
  symbolic link to it.
- Installs Zulip's various dependencies.
- Configures the various third-party services Zulip uses, including
  PostgreSQL, RabbitMQ, Memcached and Redis.
- Initializes Zulip's database.

If you'd like to deploy Zulip with these services on different
machines, check out our [deployment options documentation](deployment.md).

## Troubleshooting

**Install script.**
The Zulip install script is designed to be idempotent. This means
that if it fails, then once you've corrected the cause of the failure,
you can just rerun the script.

The install script automatically logs a transcript to
`/var/log/zulip/install.log`. In case of failure, you might find the
log handy for resolving the issue. Please include a copy of this log
file in any bug reports.

**The `zulip` user's password.**
By default, the `zulip` user doesn't
have a password, and is intended to be accessed by `su zulip` from the
`root` user (or via SSH keys or a password, if you want to set those
up, but that's up to you as the system administrator). Most people
who are prompted for a password when running `su zulip` turn out to
already have switched to the `zulip` user earlier in their session,
and can just skip that step.

**After the install script.**
If you get an error after `scripts/setup/install` completes, check
the bottom of `/var/log/zulip/errors.log` for a traceback, and consult
the [troubleshooting section](troubleshooting.md) for advice on
how to debug.

**Still having trouble?**
Please see the [troubleshooting and monitoring
guide](../production/troubleshooting.md) for additional advice and ways to get
help.
