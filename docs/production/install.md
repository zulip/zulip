# Production installation

Zulip requires a dedicated Ubuntu or Debian system as per
[the installation requirements](../production/requirements.md).
Alternatively, you can use a preconfigured
[DigitalOcean droplet](https://marketplace.digitalocean.com/apps/zulip?refcode=3ee45da8ee26),
or Zulip's [experimental Docker image](../production/deployment.html#zulip-in-docker).

Note that if you're developing for Zulip, you should install Zulip's
[development environment](../development/overview.md) instead.
If you're just looking to play around with Zulip and see what it looks like,
you can create a test organization at <https://zulip.com/new>.

## Step 1: Download the latest release

Download and unpack
[the latest server release](https://download.zulip.com/server/zulip-server-latest.tar.gz)
(**Zulip Server {{ LATEST_RELEASE_VERSION }}**) with the following commands:

```bash
cd $(mktemp -d)
curl -fLO https://download.zulip.com/server/zulip-server-latest.tar.gz
tar -xf zulip-server-latest.tar.gz
```

- If you'd like to verify the download, we
  [publish the sha256sums of our release tarballs](https://download.zulip.com/server/SHA256SUMS.txt).
- You can also
  [install a pre-release version of Zulip](../production/deployment.html#installing-zulip-from-git)
  using code from our [repository on GitHub](https://github.com/zulip/zulip/).

## Step 2: Install Zulip

To set up Zulip with the most common configuration,
run the installer as follows:

```bash
sudo -s  # If not already root
./zulip-server-*/scripts/setup/install --certbot \
    --email=YOUR_EMAIL --hostname=YOUR_HOSTNAME
```

This takes a few minutes to run, as it installs Zulip's dependencies.
For more on what the installer does, [see details below](#installer-details).

If the script returns an error,
consult [Troubleshooting](#troubleshooting) below.

#### Installer options

- `--email=you@example.com`: The email address of the person or team
  who should get support and error emails from this Zulip server.
  This becomes `ZULIP_ADMINISTRATOR` ([docs][doc-settings]) in the Zulip settings.

- `--hostname=zulip.example.com`: The user-accessible domain name for
  this Zulip server, i.e., what users will type in their web browser.
  This becomes `EXTERNAL_HOST` ([docs][doc-settings]) in the Zulip settings.

- `--self-signed-cert`: With this option, the Zulip installer
  generates a self-signed SSL certificate for the server.
  This isn't suitable for production use, but may be convenient for testing.

- `--certbot`: With this option, the Zulip installer automatically
  obtains an SSL certificate for the server [using Certbot][doc-certbot].
  If you'd prefer to acquire an SSL certificate yourself in any other way,
  it's easy to [provide it to Zulip][doc-ssl-manual].

Advanced installer options are explained
in our [deployment options][doc-deployment-options] documentation.

[doc-settings]: ../production/settings.md
[doc-certbot]: ../production/ssl-certificates.html#certbot-recommended
[doc-ssl-manual]: ../production/ssl-certificates.html#manual-install
[doc-deployment-options]: ../production/deployment.html#advanced-installer-options

## Step 3: Create a Zulip organization, and log in

On success, the install script prints a link.
If you are [restoring a backup][zulip-backups]
or importing your data from [Slack][slack-import],
or another Zulip server, stop here
and return to the import instructions.

[slack-import]: https://zulip.com/help/import-from-slack
[zulip-backups]: ../production/export-and-import.html#backups

Otherwise, open the link in a browser.
Follow the prompts to set up your organization
and your administrator account.

The link is a secure one-time-use link. If you need another
later, you can generate a new one by running
`manage.py generate_realm_creation_link` on the server. See also our
doc on running [multiple organizations on the same
server](multiple-organizations.md) if that's what you're planning to
do.

## Step 4: Configure and use

To see Zulip in action,
get some people to join you:

- [Set up outgoing email](email.md) so Zulip can confirm new users'
  email addresses and send notifications.
- Learn how to [get your organization started][realm-admin-docs]
  using Zulip at its best.

More Resources:

- Subscribe to the [Zulip announcements email
  list](https://groups.google.com/g/zulip-announce) for
  server administrators. This extremely low-traffic list is for
  important announcements, including [new
  releases](../overview/release-lifecycle.md) and security issues.
- Follow [Zulip on Twitter](https://twitter.com/zulip).
- Learn how to [configure your Zulip server settings](settings.md).
- Learn about [Backups, export and import](../production/export-and-import.md)
  and [upgrading](../production/upgrade-or-modify.md) a production Zulip
  server.

[realm-admin-docs]: https://zulip.com/help/getting-your-organization-started-with-zulip

(installer-details)=

## Details: What the installer does

The install script does several things:

- Creates the `zulip` user, which the various Zulip servers will run as.
- Creates `/home/zulip/deployments/`, which the Zulip code for this
  deployment (and future deployments when you upgrade) goes into.
  At the very end of the install process,
  the script moves the Zulip code tree it is running from (which you unpacked from a tarball above)
  to a directory there and creates `/home/zulip/deployments/current`
  as a symbolic link to it.
- Installs Zulip's dependencies.
- Configures the third-party services for Zulip,
  including PostgreSQL, RabbitMQ, Memcached and Redis.
- Initializes Zulip's database.

If you'd like to deploy Zulip with these services on different machines,
check out our [deployment options documentation](deployment.md).

## Troubleshooting

**Install script:**
The Zulip install script is designed to be idempotent.
On failure you can simply rerun it
after correcting the issue.  
The install script automatically logs a transcript to
`/var/log/zulip/install.log`,
which can be handy to resolve issues.
Please include a copy of this log file in any bug reports.

**The `zulip` user's password:**
By default, the `zulip` user doesn't have a password,
and is intended to be accessed by `su zulip` from the `root` user
(or via SSH keys or a password, if you want to set those up,
but that's up to you as the system administrator).
Most people prompted for a password when running `su zulip`
turn out to already have switched to the `zulip` user earlier in their session,
and can just skip that step.

**After the install script:**
If you get an error after `scripts/setup/install` completes,
check the bottom of `/var/log/zulip/errors.log` for a traceback,
and consult the [troubleshooting section](troubleshooting.md)
for advice on how to debug.

**Community:**
If the tips above don't help, please visit [#production help][production-help]
in the [Zulip development community server][chat-zulip-org] for realtime help,
and we will try to help you out!
Please provide details like the full traceback from the bottom of `/var/log/zulip/errors.log`
in your report (ideally in a [code block][code-block]).

[chat-zulip-org]: https://zulip.com/developer-community/
[production-help]: https://chat.zulip.org/#narrow/stream/31-production-help
[code-block]: https://zulip.com/help/code-blocks
