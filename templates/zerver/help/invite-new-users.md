# Invite new users

There are a number of ways to grant access to your Zulip organization.

* Allow **anyone to join** without an invitation.

* Allow people to join based on the **domain** of their email address.

* Send **email invitations** to up to 100 addresses at a time.

* Share a **reusable invitation link**.

This article will cover these methods in detail.

You can also manage access by
[controlling how users authenticate](/help/configure-authentication-methods)
to Zulip.  For example, you could allow anyone to join without an
invitation, but require them to authenticate via LDAP.

## Enable email signup

{start_tabs}

{tab|restrict-by-email-domain}

1. Set [default streams](/help/set-default-streams-for-new-users) for new users.

{settings_tab|organization-permissions}

1. Find the section **Joining the organization**.

1. Set **Are invitations required for joining the organization** to **No**.

1. Set **Restrict email domains of new users?** to
   **Restrict to a list of domains**.

1. Enter any number of domains. For each domain, check or uncheck
   **Allow subdomains**.

1. Click **Save changes**.

{tab|allow-anyone-to-join}

1. Set [default streams](/help/set-default-streams-for-new-users) for new users.

{settings_tab|organization-permissions}

1. Find the section **Joining the organization**.

1. Set **Are invitations required for joining the organization** to **No**.

1. Set **Restrict email domains of new users?** to either
   **Don't allow disposable email addresses** (recommended) or **No**.

1. Click **Save changes**.

{end_tabs}

Before anyone joins your organization this way, we'll send a validation link
to verify their email address.

## Send invitations

By default, organization admins and members can send
invitations. Organization admins can also change who can send invitations.

Note that on most Zulip servers (including Zulip Cloud), email invitations
and reusable invitation links expire 10 days after they are sent.

{start_tabs}

{tab|send-email-invitations}

{relative|gear|invite}

1. Enter a list of email addresses.

1. Decide whether the users should join as admins, members, or guests.

1. Select which streams they should join. If you send invitations often, you
   may want to configure a set of
   [default streams](/help/set-default-streams-for-new-users).

1. Click **Invite**.

!!! warn ""
    You will only see **Invite users** in the gear menu if you have
    permission to invite users.

{tab|share-an-invite-link}

{relative|gear|invite}

1. Click **Generate invite link**.

1. Decide whether users using the link should join as admins, members, or
   guests.

1. Select which streams they should join. If you send invitations often, you
   may want to configure a set of
   [default streams](/help/set-default-streams-for-new-users).

1. Click **Generate invite link**.

1. Copy the link, and send it to anyone you'd like to invite.

!!! warn ""
    You will only see **Invite users** in the gear menu if you have
    permission to invite users.

{end_tabs}

## Change who can send invitations

By default, organization admins and members can send invitations. You can
restrict invites to admins only.

{start_tabs}

{settings_tab|organization-permissions}

1. Under Joining the organization, set
   **Are invitations required for joining the organization?** to
   **Yes. Only admins can send invitations**.

1. Click **Save changes**.

{end_tabs}

## Manage pending invitations

Organization administrators can revoke or resend any invitation or reusable
invitation link.

{start_tabs}

{settings_tab|invites-list-admin}

1. From here, you can view pending invitations, **Revoke** email invitations
   and invitation links, or **Resend** email invitations.

{end_tabs}
