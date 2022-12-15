When user accounts are imported, users initially do not have passwords
configured. There are a few options for how users can log in for the first time.

!!! tip ""

    For security reasons, passwords are never exported.

### Allow users to log in with non-password authentication

When you create your organization, users will immediately be able to log in with
[authentication methods](/help/configure-authentication-methods) that do not
require a password. Zulip offers a variety of authentication methods, including
Google, GitHub, GitLab, Apple, LDAP and [SAML](/help/saml-authentication).

### Send password reset emails to all users

You can send password reset emails to all users in your organization, which
will allow them to set an initial password.

If you imported your organization into Zulip Cloud, simply e-mail
[support@zulip.com](mailto:support@zulip.com) to request this.

!!! warn ""

    To avoid confusion, first make sure that the users in your
    organization are aware that their account has been moved to
    Zulip, and are expecting to receive a password reset email.

#### Send password reset emails (self-hosted organization)

{start_tabs}

{tab|default-subdomain}

1. To test the process, start by sending yourself a password reset email by
   using the following command:

     ```
     ./manage.py send_password_reset_email -u username@example.com
     ```

1. When ready, send password reset emails to all users by
   using the following command:

     ```
     ./manage.py send_password_reset_email -r '' --all-users
     ```

{tab|custom-subdomain}

1. To test the process, start by sending yourself a password reset email by
   using the following command:

     ```
     ./manage.py send_password_reset_email -u username@example.com
     ```

1. When ready, send password reset emails to all users by
   using the following command:

     ```
     ./manage.py send_password_reset_email -r <subdomain> --all-users
     ```

{end_tabs}

### Manual password resets

Alternatively, users can reset their own passwords by following the instructions
on your Zulip organization's login page.
