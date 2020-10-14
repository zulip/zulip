# Change organization URL

Zulip supports changing the URL for an organization.  Changing the
organization URL is a disruptive operation for users:

* Users will be logged out of existing sessions on the web, mobile and
  desktop apps and need to log in again.
* Any [API clients](/api) or [integrations](/integrations) will need
  to be updated to point to the new organization URL.

We recommend using a [wildcard
mention](/help/mention-a-user-or-group#mention-everyone-on-a-stream)
in an announcement stream to notify users that they need to update
their clients.

If you're using Zulip Cloud (E.g. `https://example.zulipchat.com`),
you can request a change by emailing support@zulip.com.

## Self-hosting

If you're self-hosting, you can change the root domain of your server
by changing the `EXTERNAL_HOST` [setting][zulip-settings].  If you're
[hosting multiple organizations][zulip-multiple-organizations] and
want to change the subdomain for one of them, you can use
`do_realm_change_subdomain(realm, "new_subdomain")` in a [management
shell][management-shell].

[zulip-settings]: https://zulip.readthedocs.io/en/stable/production/settings.html
[zulip-multiple-organizations]: https://zulip.readthedocs.io/en/stable/production/multiple-organizations.html
[management-shell]: https://zulip.readthedocs.io/en/stable/production/management-commands.html#manage-py-shell
