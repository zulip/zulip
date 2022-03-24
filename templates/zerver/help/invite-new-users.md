# Invite new users

There are a number of ways to grant access to your Zulip organization:

* Allow **anyone to join** without an invitation.

* Allow people to join based on the **domain** of their email address.

* Send **email invitations**.

* Share a **reusable invitation link**.

You can also manage access by
[controlling how users authenticate](/help/configure-authentication-methods)
to Zulip.  For example, you could allow anyone to join without an
invitation, but require them to authenticate via LDAP.

When you invite users, you can:

* Set the [role](/help/roles-and-permissions) that they will have when
  they join.

* Configure the streams they will automatically be added to.

## Enable email signup

{start_tabs}

1. Set [default streams](/help/set-default-streams-for-new-users) for new users.

{settings_tab|organization-permissions}

1. Under **Joining the organization**, toggle
   **Invitations are required for joining this organization**.

1. From the **Restrict email domains of new users?** dropdown menu,
   select between:

     - **No restrictions**, which will

     - **Don't allow disposable emails**, which will

     - **Restrict to a list of domains**, which will


{!save-changes.md!}

{end_tabs}

!!! warn ""

    **Note**: Before anyone joins your organization this way, a validation
    link will be sent to verify their email address.

## Restrict email domains

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Joining the organization**, toggle
   **Invitations are required for joining this organization**.

1. Set **Restrict email domains of new users?** to
   **Restrict to a list of domains**.

1. Click **Configure** to add any number of domains.
   For each domain, you can toggle **Allow subdomains**.
   When you are done adding domains, click **Close**.

{!save-changes.md!}

{end_tabs}

## Send invitations

You will only see an **Invite users** option if you have permission to
invite users to the organization.

{start_tabs}

{tab|send-email-invitations}

{relative|gear|invite}

1. Enter a list of email addresses.

1. Select when the invitation will expire.

1. Select what [role](/help/roles-and-permissions) the users will join as.

1. Configure which streams they will be added to. If you send invitations
   often, you may want to configure a set of
   [default streams](/help/set-default-streams-for-new-users).

1. Click **Invite**.

!!! warn ""

    **Note**: The number of email invites you can send in a day is
    limited in the free plan. [Contact us](/help/contact-support)
    if you hit the limit and want to invite more users.

{tab|share-an-invite-link}

{relative|gear|invite}

1. Click **Generate invite link**.

1. Select when the invitation will expire.

1. Select what [role](/help/roles-and-permissions) the users will join as.

1. Configure which streams they will be added to. If you send invitations
   often, you may want to configure a set of
   [default streams](/help/set-default-streams-for-new-users).

1. Click **Generate invite link**.

1. Copy the link, and send it to anyone you'd like to invite.

!!! warn ""

    **Note**: Only organization administrators can create these reusable
    invitation links.

{end_tabs}

## Change who can send invitations

{!owner-only.md!}

You can restrict the ability to invite new users to join your
Zulip organization to specific [roles](/help/roles-and-permissions).

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Joining the organization**, configure
   **Who can invite users to this organization**.

{!save-changes.md!}

{end_tabs}

## Manage pending invitations

Organization owners can revoke or resend any invitation or reusable
invitation link. Organization administrators can do the same except
for invitations for the organization owners role.

{start_tabs}

{settings_tab|invites-list-admin}

1. From there, you can view pending invitations, **Revoke** email
   invitations and invitation links, or **Resend** email invitations.

{end_tabs}

## Related articles

* [Stream permissions](/help/stream-permissions)
* [Roles and permissions](/help/roles-and-permissions)
