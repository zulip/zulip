# Restrict account creation

{!owner-only.md!}

Each Zulip account is associated with an email address. If your organization
allows multiple authentication methods, it doesn't matter which one is used to
create an account. All authentication methods will work for all users in your
organization, provided that they are associated with the account email. To log
in with email, users are required to verify their email account by clicking on a
validation link.

Zulip provides a number of configuration options to control who can create a new
account and how users access their accounts:

* You can [require an invitation](#set-whether-invitations-are-required-to-join)
  to sign up (default), or you can [allow anyone to
  join](#set-whether-invitations-are-required-to-join) without an invitation.

* You can [restrict the ability to invite new users](#change-who-can-send-invitations) to
 join your Zulip organzation to specific [roles](/help/roles-and-permissions).

Regardless of whether invitations are required, you can:

* [Configure allowed authentication
  methods](/help/configure-authentication-methods).

* [Restrict sign-ups to a fixed list of allowed
  domains](#restrict-sign-ups-to-a-list-of-domains)
  (including subdomains). For example, you can require users to sign up with
  the email domain for your business or university.

* Disallow signups with known [disposable email
  address](https://en.wikipedia.org/wiki/Disposable_email_address). This
  is recommended for open organizations to help protect against abuse.

## Set whether invitations are required to join

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Joining the organization**, toggle **Invitations are required for
   joining this organization**.

{!save-changes.md!}

{end_tabs}

## Change who can send invitations

{start_tabs}

{settings_tab|organization-permissions}

1. Under **Joining the organization**, configure
   **Who can send email invitations to new users** and
   **Who can create reusable invitation links**.

{!save-changes.md!}

{end_tabs}

## Configuring email domain restrictions

### Restrict sign-ups to a list of domains

{start_tabs}

{settings_tab|organization-permissions}

1. Set **Restrict email domains of new users?** to
   **Restrict to a list of domains**.

1. Click **Configure** to add any number of domains. For each domain, you can
   toggle **Allow subdomains**.

1. When you are done adding domains, click **Close**.

{!save-changes.md!}

{end_tabs}

### Don't allow disposable domains

{start_tabs}

{settings_tab|organization-permissions}

1. Set **Restrict email domains of new users?** to
   **Don't allow disposable emails**.

{!save-changes.md!}

{end_tabs}

### Allow all email domains

{start_tabs}

{settings_tab|organization-permissions}

1. Set **Restrict email domains of new users?** to
   **No restrictions**.

{!save-changes.md!}

{end_tabs}

## Related articles

* [Configure authentication methods](/help/configure-authentication-methods)
* [Invite new users](/help/invite-new-users)
* [Set default channels for new users](/help/set-default-channels-for-new-users)
* [Configure default new user settings](/help/configure-default-new-user-settings)
