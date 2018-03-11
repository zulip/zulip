# Zulip in production

To play around with Zulip and see what it looks like, check out the
[Zulip community server](../contributing/chat-zulip-org.html) or create a test organization
on <https://zulipchat.com>.

If you like what you see, you can set up Zulip for your team by
installing a production Zulip server.  These pages will walk you
through how.

## Requirements

You'll [need a few things](../production/requirements.html) to run a production
Zulip server.  Key requirements include:
* a dedicated server or VM, running Ubuntu, with at least 2GB of RAM
  (or 4GB for a large site);
* a valid DNS name and SSL certificates;
* a way to send outgoing email.

See [the requirements page](../production/requirements.html) for more details,
including free options [for SSL](ssl-certificates.html) and [for
outgoing email](email.html#free-outgoing-email-services) if you don't have
those already.

## Install

Follow [the install instructions](../production/install.html).  You'll download
the built release tarball, run the Zulip install script, and configure
a handful of required settings; then create your Zulip organization
through your new server's web interface.

## Running

You now have a running Zulip install!

* Read [our advice on helping your community][realm-admin-docs] make
  the most of Zulip.

* [Customize Zulip](settings.html) by configuring the server-level settings.

* Read about Zulip's support for backups, monitoring, and
  other [important production considerations](../production/maintain-secure-upgrade.html).

[realm-admin-docs]: https://zulipchat.com/help/getting-your-organization-started-with-zulip
