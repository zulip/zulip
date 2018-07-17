# Restrict name and email changes

{!admin-only.md!}

# Prevent users from changing their email address

By default, any user can change their own email address by going through an
email confirmation process that confirms they own both the account and new
email address. You can enable a setting that prevents all email address
changes via the Zulip UI. This is especially useful for organizations
that are using LDAP or another a Single Sign-On solution where a user's
account is managed elsewhere.

{settings_tab|organization-permissions}

2. Under the **User identity**, select **Prevent users from changing their email address**.

{!save-changes.md!} organization settings.

# Prevent users from changing their name

By default, [users can change their name](/help/change-your-name) on their
own, but administrators can enable a setting that requires an administrator to
change a users name via the Zulip UI.

{settings_tab|organization-permissions}

2. Under the **User identity**, select **Prevent users from changing their name**.

{!save-changes.md!}


