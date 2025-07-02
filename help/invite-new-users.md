# Invite new users

You can invite users to join your organization by sending out email invitations,
or creating reusable invitation links to share.

Prior to inviting users to your organization, it is recommended that administrators:

* Configure [default settings](/help/configure-default-new-user-settings) for
  new users.

* Configure the [organization language for automated messages and invitation
  emails][org-lang] for your organization.

When you invite users, you can:

* Set the [role](/help/user-roles) that they will have when
  they join.

* Configure which [channels](/help/introduction-to-channels) they will be
  subscribed to. The organization's [default
  channels](/help/set-default-channels-for-new-users) will be preselected.

* Configure which [groups](/help/user-groups) they will be added to.

Organization administrators can
[configure](/help/restrict-account-creation#change-who-can-send-invitations) who
is allowed to invite users to the organization. You will only see an **Invite
users** menu option if you have permission to invite users.

## Send email invitations

{start_tabs}

{!invite-users.md!}

1. Enter a list of email addresses.

1. Toggle **Send me a direct message when my invitation is accepted**,
   to receive a notification when an invitation is accepted.

1. Select when the invitations will expire.

1. Select what [role](/help/user-roles) the users will join as.

1. Configure which [channels](/help/introduction-to-channels) they will be subscribed
   to.

1. Configure which [groups](/help/user-groups) they will be added to.

1. Click **Invite**.

!!! warn ""
    **Note**: As an anti-spam measure, the number of email invitations
    you can send in a day is limited on the Zulip Cloud Free plan. If
    you hit the limit and need to invite more users, consider creating an
    [invitation link](#create-a-reusable-invitation-link) and sharing it
    with your users directly, or [contact support](/help/contact-support)
    to ask for a higher limit.

{end_tabs}

!!! warn ""
    **Warning**: When an account is created by accepting an email
    invitation, the user is immediately logged in to their new account.
    Any restrictions on [allowed authentication
    methods](/help/configure-authentication-methods) are not applied.

## Example email invitation

![Email invitation](/static/images/help/example-invitation-email.png)

## Create a reusable invitation link

{start_tabs}

{!invite-users.md!}

1. Select **Invitation link**.

1. Select when the invitation will expire.

1. Select what [role](/help/user-roles) the users will join as.

1. Configure which [channels](/help/introduction-to-channels) they will be subscribed
   to.

1. Configure which [groups](/help/user-groups) they will be added to.

1. Click **Create link**.

1. Copy the link, and send it to anyone you'd like to invite.

{end_tabs}

## Manage pending invitations

Organization owners can revoke or resend any invitation or reusable
invitation link. Organization administrators can do the same except
for invitations for the organization owners role.

### Revoke an invitation

{start_tabs}

{settings_tab|invitations}

1. Select the **Invitations** tab.

1. Find the invitation you want to revoke.

1. Click the **Revoke** (<i class="zulip-icon zulip-icon-trash"></i>) icon next to the invitation.

{end_tabs}

### Resend an invitation

{start_tabs}

{settings_tab|invitations}

1. Select the **Invitations** tab.

1. Find the invitation you want to resend.

1. Click the **Resend** (<i class="zulip-icon zulip-icon-send-dm"></i>) icon next to the invitation.

{end_tabs}

!!! warn ""
    **Note:** You can **revoke** both email invitations and invitation links,
    but you can **resend** only email invitations.

## Related articles

* [Restrict account creation](/help/restrict-account-creation)
* [Set default channels for new users](/help/set-default-channels-for-new-users)
* [Configure default new user settings](/help/configure-default-new-user-settings)
* [Configure organization language for automated messages and invitation emails][org-lang]
* [User roles](/help/user-roles)
* [User groups](/help/user-groups)
* [Joining a Zulip organization](/help/join-a-zulip-organization)

[org-lang]: /help/configure-organization-language
