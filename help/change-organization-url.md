# Change organization URL

Zulip supports changing the URL for an organization.  Changing the
organization URL is a disruptive operation for users:

* Users will be logged out of existing sessions on the web, mobile and
  desktop apps and need to log in again.
* Any [API clients](/api) or [integrations](/integrations/) will need
  to be updated to point to the new organization URL.

We recommend using a [wildcard
mention](/help/mention-a-user-or-group#mention-everyone-on-a-stream)
in an announcement stream to notify users that they need to update
their clients.

If you're using Zulip Cloud (E.g. `https://example.zulipchat.com`),
you can request a change by emailing support@zulip.com. Custom domains
(i.e. those that do not have the form `example.zulipchat.com`) have a
maintenance cost for our operational team and thus are only available
for paid plans.

## Self-hosting

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
