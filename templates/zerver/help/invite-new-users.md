# Invite new users

When you invite users, you can:

* Set the [role](/help/roles-and-permissions) that they will have when
  they join.

* Configure which streams they will be added to. The organization's
  [default streams](/help/set-default-streams-for-new-users) will be preselected.

Your organization may also want to configure [default
settings](/help/configure-default-new-user-settings) for new users.

## Send e-mail invitations

!!! warn ""
    You will only see an **Invite users** option if you
    [have permission](/help/restrict-account-creation#change-who-can-send-invitations)
    to invite users to the organization.

{start_tabs}

{relative|gear|invite}

1. Enter a list of email addresses.

1. Select when the invitation will expire.

1. Select what [role](/help/roles-and-permissions) the users will join as.

1. Configure which streams they will be added to.

1. Click **Invite**.

!!! warn ""

    **Note**: As an anti-spam measure, the number of email invites you can send in a day is
    limited on the Zulip Cloud Free plan. [Contact support](/help/contact-support)
    if you hit the limit and want to invite more users.

{end_tabs}

!!! warn ""
    **Warning**: Creating an account using a personal invitation link does
    not require the user to authenticate using a [configured
    authentication method](/help/configure-authentication-methods).

## Create an invitation link

{!admin-only.md!}

{start_tabs}

{relative|gear|invite}

1. Click **Generate invite link**.

1. Select when the invitation will expire.

1. Select what [role](/help/roles-and-permissions) the users will join as.

1. Configure which streams they will be added to.

1. Click **Generate invite link**.

1. Copy the link, and send it to anyone you'd like to invite.

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

* [Restrict account creation](/help/restrict-account-creation)
* [Set default streams for new users](/help/set-default-streams-for-new-users)
* [Configure default new user settings](/help/configure-default-new-user-settings)
* [Roles and permissions](/help/roles-and-permissions)
