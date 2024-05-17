# Change organization URL

{!owner-only.md!}

Zulip supports changing the URL for an organization.  Changing the
organization URL is a disruptive operation for users:

* Users will be logged out of existing sessions on the web, mobile and
  desktop apps and need to log in again.
* Any [API clients](/api/) or [integrations](/integrations/) will need
  to be updated to point to the new organization URL.

We recommend using a [wildcard
mention](/help/mention-a-user-or-group#mention-everyone-on-a-channel)
in an announcement channel to notify users that they need to update
their clients.

## Change your Zulip Cloud subdomain

Zulip Cloud organizations are generally hosted at `<subdomain>.zulipchat.com`,
with the subdomain chosen when the organization was created. Organization
[owners](/help/roles-and-permissions) can request to change the subdomain.

{start_tabs}

Please e-mail [support@zulip.com](mailto:support@zulip.com) with the following
information:

1. Your organization's current subdomain.

1. The subdomain you would like to move your organization to.

{end_tabs}

## Move to a custom URL on Zulip Cloud

{!cloud-plus-only.md!}

Because maintaining custom URLs requires effort from our operational team,
this feature is available only for organizations with 25+ [Zulip Cloud
Plus](https://zulip.com/plans/#cloud) licenses.

{start_tabs}

Please e-mail [support@zulip.com](mailto:support@zulip.com) with the following
information:

1. Your organization's current URL.

1. The URL you would like to move your organization to.

{end_tabs}

## Change the URL for your self-hosted server

If you're self-hosting, you can change the root domain of your Zulip
server by changing the `EXTERNAL_HOST` [setting][zulip-settings].  If
you're [hosting multiple organizations][zulip-multiple-organizations]
and want to change the subdomain for one of them, you can do this
using the `change_realm_subdomain` [management command][management-commands].

In addition to configuring Zulip as detailed here, you also need to
generate [SSL certificates][ssl-certificates] for your new domain.

[ssl-certificates]: https://zulip.readthedocs.io/en/stable/production/ssl-certificates.html
[zulip-settings]: https://zulip.readthedocs.io/en/stable/production/settings.html
[zulip-multiple-organizations]: https://zulip.readthedocs.io/en/stable/production/multiple-organizations.html
[management-commands]: https://zulip.readthedocs.io/en/stable/production/management-commands.html#other-useful-manage-py-commands
