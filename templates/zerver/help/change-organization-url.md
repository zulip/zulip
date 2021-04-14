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
you can request a change by emailing support@zulip.com. Custom domains
(i.e. those that do not have the form `example.zulipchat.com`) have a
maintenance cost for our operational team and thus are only available
for paid plans.

## Self-hosting

If you're self-hosting, you can change the root domain of your Zulip
server by changing the `EXTERNAL_HOST` [setting][zulip-settings].  If
you're [hosting multiple organizations][zulip-multiple-organizations]
and want to change the subdomain for one of them, you can follow these
steps:

{start_tabs}

1. Get the `string_id` for your organization as [described here][find-string-id]

2. Run the following commands in a [management shell][management-shell]:

    ```
    realm = get_realm("string_id")
    do_change_realm_subdomain(realm, "new_subdomain")
    ```

{end_tabs}

[zulip-settings]: https://zulip.readthedocs.io/en/stable/production/settings.html
[zulip-multiple-organizations]: https://zulip.readthedocs.io/en/stable/production/multiple-organizations.html
[management-shell]: https://zulip.readthedocs.io/en/stable/production/management-commands.html#manage-py-shell
[find-string-id]: https://zulip.readthedocs.io/en/stable/production/management-commands.html#accessing-an-organization-s-string-id
