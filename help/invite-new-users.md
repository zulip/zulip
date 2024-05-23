# Invite new users

You can invite users to join your organization by sending out email invitations,
or creating reusable invitation links to share.

Prior to inviting users to your organization, it is recommended that administrators:

* Configure [default settings](/help/configure-default-new-user-settings) for
  new users.

* Configure the [organization language for automated messages and invitation
  emails][org-lang] for your organization.

When you invite users, you can:

* Set the [role](/help/roles-and-permissions) that they will have when
  they join.

* Configure which channels they will be added to. The organization's
  [default channels](/help/set-default-channels-for-new-users) will be preselected.

Organization administrators can
[configure](/help/restrict-account-creation#change-who-can-send-invitations)
which [roles](/help/roles-and-permissions) have permission to invite users to
the organization. You will only see an **Invite users** menu option if you have
permission to invite users.

## Send email invitations

{start_tabs}

{!invite-users.md!}

1. Click **Send an email**.

1. Enter a list of email addresses.

1. Select when the invitation will expire.

1. Select what [role](/help/roles-and-permissions) the users will join as.

1. Configure which channels they will be added to.

1. Click **Invite**.

!!! warn ""
    **Note**: As an anti-spam measure, the number of email invites you can send in a day is
    limited on the Zulip Cloud Free plan. [Contact support](/help/contact-support)
    if you hit the limit and want to invite more users.

{end_tabs}

!!! warn ""
    **Warning**: When an account is created by accepting an email
    invitation, the user is immediately logged in to their new account.
    Any restrictions on [allowed authentication
    methods](/help/configure-authentication-methods) are not applied.

## Create a reusable invitation link

{start_tabs}

{!invite-users.md!}

1. Click **Generate invite link**.

1. Select when the invitation will expire.

1. Select what [role](/help/roles-and-permissions) the users will join as.

1. Configure which channels they will be added to.

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
* [Set default channels for new users](/help/set-default-channels-for-new-users)
* [Configure default new user settings](/help/configure-default-new-user-settings)
* [Configure organization language for automated messages and invitation emails][org-lang]
* [Roles and permissions](/help/roles-and-permissions)
* [Joining a Zulip organization](/help/join-a-zulip-organization)

[org-lang]: /help/configure-organization-language
