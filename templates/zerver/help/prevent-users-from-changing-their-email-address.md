# Prevent users from changing their email address

{!admin-only.md!}

By default, any user can change their own email address by going
through an email confirmation process that confirms they own both the
account and new email address.

For organizations that are using LDAP or another a Single Sign-On
solution where a user's account is managed elsewhere, you can enable a
setting that prevents them from changing their own email address via
the Zulip UI.

{!go-to-the.md!} [Organization permissions](/#organization/organization-permissions)
{!admin.md!}

2. Select the **Prevent users from changing their email address** checkbox
under the **User identity** section.

{!save-changes.md!} organization settings.
