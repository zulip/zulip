# Restrict name and email changes

{!admin-only.md!}

## Restrict name changes

By default, any user can [change their name](/help/change-your-name).
You can instead prevent users from changing their name. This setting is
especially useful if user names are managed via an external source, and
synced into Zulip via the [Zulip API](/api/), [LDAP][ldap-sync-data] or
another method.

!!! tip ""

    Organization administrators can always [change anyone's
    name](/help/change-a-users-name).

{start_tabs}

{settings_tab|organization-permissions}

1. Under **User identity**, select **Prevent users from changing their
   name**.

{!save-changes.md!}

{end_tabs}

## Restrict email changes

By default, any user can [change their email address][change-email].
However, you can instead prevent users from changing their email
address. This setting is especially useful for organizations that
are using [LDAP][ldap-sync-data] or another single sign-on solution
to manage user emails.

!!! tip ""

    Organization administrators can always change their own email
    address.

{start_tabs}

{settings_tab|organization-permissions}

1. Under **User identity**, select **Prevent users from changing their
   email address**.

{!save-changes.md!}

{end_tabs}

## Require unique names

You can require users to choose unique names when joining your organization, or
changing their name. This helps prevent accidental creation of duplicate
accounts, and makes it harder to impersonate other users.

When you turn on this setting, users who already have non-unique names are not
required to change their name.

{start_tabs}

{settings_tab|organization-permissions}

1. Under **User identity**, select **Require unique names**.

{!save-changes.md!}

{end_tabs}

[change-email]: /help/change-your-email-address
[ldap-sync-data]: https://zulip.readthedocs.io/en/stable/production/authentication-methods.html#synchronizing-data
