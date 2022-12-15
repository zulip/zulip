# Restrict profile picture change

{!admin-only.md!}

By default, any user can [change their profile
picture](/help/change-your-profile-picture).  You can instead prevent
users from changing their profile picture (primarily useful in
organizations that are [synchronizing profile pictures from
LDAP][ldap-sync]) or a similar directory.

[ldap-sync-avatars]: https://zulip.readthedocs.io/en/latest/production/authentication-methods.html#synchronizing-avatars

{start_tabs}

{settings_tab|organization-permissions}

2. Under the **User identity**, select **Prevent users from changing their avatar**.

{!save-changes.md!}

{end_tabs}
