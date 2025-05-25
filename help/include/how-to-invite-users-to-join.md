{start_tabs}
{tab|require-invitations}

1. [Configure allowed authentication
   methods](/help/configure-authentication-methods). Zulip offers a variety of
   authentication methods, including email/password, Google, GitHub, GitLab,
   Apple, LDAP and [SAML](/help/saml-authentication). Users can [log
   in][logging-in] with any allowed authentication method, regardless of how
   they signed up.

1. Invite users by [sending email invitations][email-invitations] or
   sharing a [reusable invitation link][invitation-links].

{tab|allow-anyone-to-join}

1. Allow users to [join without an invitation][set-if-invitations-required].

1. Configure the appropriate [email domain restrictions][restrict-email-domain]
   for your organization.

1. Share a link to your registration page, which is
   https://your-org.zulipchat.com for Zulip Cloud organizations.

{tab|imported-organizations}

1. [Configure allowed authentication
   methods](/help/configure-authentication-methods). Zulip offers a variety of
   authentication methods, including email/password, Google, GitHub, GitLab,
   Apple, LDAP and [SAML](/help/saml-authentication). Users can immediately [log
   in][logging-in] with any allowed authentication method that does not require
   a password.

1. Share a link to your Zulip organization, which is
   https://your-org.zulipchat.com on Zulip Cloud.

1. *(optional)* To log in with an email/password, users will need to set their
   initial password. You can:

    - Automatically send password reset emails to all users in your
     organization. If you imported your organization into Zulip Cloud, simply
     email [support@zulip.com](mailto:support@zulip.com) to request this. Server
     administrators for self-hosted organizations should follow [these
     instructions](/help/import-from-slack#send-password-reset-emails-to-all-users).

    - Let users know that they can [request a password
     reset](/help/change-your-password#if-youve-forgotten-or-never-had-a-password)
     on your organization's login page.

{end_tabs}

[email-invitations]:/help/invite-new-users#send-email-invitations
[invitation-links]: /help/invite-new-users#create-a-reusable-invitation-link
[set-if-invitations-required]: /help/restrict-account-creation#set-whether-invitations-are-required-to-join
[restrict-email-domain]: /help/restrict-account-creation#configuring-email-domain-restrictions
[logging-in]: /help/logging-in
