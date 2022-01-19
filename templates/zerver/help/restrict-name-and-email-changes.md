# Restrict name and email changes

{!admin-only.md!}

## Prevent users from changing their name

By default, any user can [change their name](/help/change-your-name). You
can instead prevent users from changing their name. Organization
administrators can always [change anyone's name](/help/change-a-users-name).

This setting is especially useful if user names are managed via an external
source, and synced into Zulip via the [Zulip API](/api) or another method.

{start_tabs}

{settings_tab|organization-permissions}

2. Under the **User identity**, select **Prevent users from changing their name**.

{!save-changes.md!}

{end_tabs}

## Prevent all email changes

By default, any user can
[change their email address](/help/change-your-email-address). However, you
can instead prevent all email changes. This is especially useful for
organizations that are using LDAP or a another single
sign-on solution to manage user emails.

{start_tabs}

{settings_tab|organization-permissions}

2. Under **User identity**, select **Prevent users from changing their email address**.

{!save-changes.md!}

{end_tabs}
