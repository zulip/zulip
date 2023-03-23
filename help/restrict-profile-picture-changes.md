# Restrict profile picture change

{!admin-only.md!}

By default, any user can [change their profile picture][change-avatar].
You can instead prevent users from changing their profile picture. This
setting is primarily useful in organizations that are [synchronizing
profile pictures from LDAP][ldap-sync-avatars] or a similar directory.

!!! tip ""

    Organization administrators can always change their own profile
    picture.

{start_tabs}

{settings_tab|organization-permissions}

1. Under **User identity**, select **Prevent users from changing their
   avatar**.

{!save-changes.md!}

{end_tabs}

[change-avatar]: /help/change-your-profile-picture
[ldap-sync-avatars]: https://zulip.readthedocs.io/en/stable/production/authentication-methods.html#synchronizing-avatars
