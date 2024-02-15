# Install a Zulip server

You can choose from several convenient options for hosting Zulip:

- Follow these instructions to **install a self-hosted Zulip server on a system
  of your choice**.
- Use a preconfigured
  [DigitalOcean droplet](https://marketplace.digitalocean.com/apps/zulip?refcode=3ee45da8ee26)
- Use Zulip's [experimental Docker image](deployment.md#zulip-in-docker).
- Use [Zulip Cloud](https://zulip.com/plans/) hosting. Read our [guide to choosing between Zulip Cloud and
  self-hosting](https://zulip.com/help/getting-your-organization-started-with-zulip#choosing-between-zulip-cloud-and-self-hosting).

To **import data** from [Slack][slack-import], [Mattermost][mattermost-import], [Rocket.Chat][rocketchat-import], [Gitter][gitter-import], [Zulip Cloud][zulip-cloud-import], or [another Zulip
server][zulip-server-import], follow the linked instructions.

You can **try out Zulip** before setting up your own server by [checking
it out](https://zulip.com/try-zulip/) in the Zulip development community, or
[creating a free test organization](https://zulip.com/new/) on Zulip Cloud.

:::{note}
These instructions are for self-hosting Zulip. To
[contribute](../contributing/contributing.md) to the project, set up the
[development environment](../development/overview.md).
:::

## Installation process overview

0. [Set up a base server](#step-0-set-up-a-base-server)
1. [Download the latest release](#step-1-download-the-latest-release)
1. [Install Zulip](#step-2-install-zulip)
1. [Create a Zulip organization, and log in](#step-3-create-a-zulip-organization-and-log-in)

That's it! Once installation is complete, you can
[configure](settings.md) Zulip to suit your needs.

## Step 0: Set up a base server

Provision and log in to a fresh Ubuntu or Debian system in your preferred
hosting environment that satisfies the [installation
requirements](requirements.md) for your expected usage level.

## Step 1: Download the latest release

Download and unpack [the latest server
release](https://download.zulip.com/server/zulip-server-latest.tar.gz)
(**Zulip Server {{ LATEST_RELEASE_VERSION }}**) with the following commands:

```bash
cd $(mktemp -d)
curl -fLO https://download.zulip.com/server/zulip-server-latest.tar.gz
tar -xf zulip-server-latest.tar.gz
```

To verify the download, see [the sha256sums of our release
tarballs](https://download.zulip.com/server/SHA256SUMS.txt).

## Step 2: Install Zulip

To set up Zulip with the most common configuration, run the installer as
follows:

```bash
sudo -s  # If not already root
./zulip-server-*/scripts/setup/install --certbot \
    --email=YOUR_EMAIL --hostname=YOUR_HOSTNAME
```

This takes a few minutes to run, as it installs Zulip's dependencies.
For more information, see [installer details](deployment.md#zulip-installer-details)
and [troubleshooting](#troubleshooting).

#### Installer options

- `--email=it-team@example.com`: The email address for the **person or team who
  maintains the Zulip installation**. Zulip users on your server will see this
  as the contact email in automated emails, on help pages, on error pages, etc.
  You can later configure a display name for your contact email with the
  `ZULIP_ADMINISTRATOR` [setting][doc-settings].

- `--hostname=zulip.example.com`: The user-accessible domain name for this Zulip
  server, i.e., what users will type in their web browser. This becomes
  `EXTERNAL_HOST` in the Zulip [settings][doc-settings].

- `--certbot`: With this option, the Zulip installer automatically obtains an
  SSL certificate for the server [using Certbot][doc-certbot], and configures a
  cron job to renew the certificate automatically. If you prefer to acquire an
  SSL certificate another way, it's easy to [provide it to
  Zulip][doc-ssl-manual].

- `--self-signed-cert`: With this option, the Zulip installer
  generates a self-signed SSL certificate for the server. This isn't
  suitable for production use, but may be convenient for testing.

For advanced installer options, see our [deployment options][doc-deployment-options]
documentation.

:::{important}

If you are importing data, stop here and return to the import instructions for
[Slack][slack-import], [Mattermost][mattermost-import],
[Rocket.Chat][rocketchat-import], [Gitter][gitter-import], [Zulip
Cloud][zulip-cloud-import], [a server backup][zulip-backups], or [another Zulip
server][zulip-server-import].

:::

[doc-settings]: settings.md
[doc-certbot]: ssl-certificates.md#certbot-recommended
[doc-ssl-manual]: ssl-certificates.md#manual-install
[doc-deployment-options]: deployment.md#advanced-installer-options
[zulip-backups]: export-and-import.md#backups
[slack-import]: https://zulip.com/help/import-from-slack
[mattermost-import]: https://zulip.com/help/import-from-mattermost
[rocketchat-import]: https://zulip.com/help/import-from-rocketchat
[gitter-import]: https://zulip.com/help/import-from-gitter
[zulip-cloud-import]: export-and-import.md#import-into-a-new-zulip-server
[zulip-server-import]: export-and-import.md#import-into-a-new-zulip-server

## Step 3: Create a Zulip organization, and log in

When the installation process is complete, the install script prints a secure
one-time-use organization creation link. Open this link in your browser, and
follow the prompts to set up your organization and your own user account. Your
Zulip organization is ready to use!

:::{note}
You can generate a new organization creation link by running `manage.py
generate_realm_creation_link` on the server. See also our guide on running
[multiple organizations on the same server](multiple-organizations.md).
:::

## Getting started with Zulip

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
