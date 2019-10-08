# Logging in

By default, Zulip allows you to log with an email/password pair, a Google account, or
a GitHub account.

Organization administrators can
[add other authentication methods](configure-authentication-methods),
including SSO or LDAP integration, or disable any of the methods above.

To log in, go to your organization's Zulip URL and follow the on-screen instructions.

!!! tip ""
    You can log in with any method, regardless of how you signed up. E.g. if
    you originally signed up using your Google account, you can later log in
    using GitHub, as long as your Google account and GitHub account use the
    same email address.

## Troubleshooting

### I don't know my Zulip URL

Some ideas:

* If you know your organization is hosted on
  [zulipchat.com](https://zulipchat.com), go to
  [find my account](https://zulipchat.com/accounts/find/) and enter the email
  address that you signed up with.

* Try guessing the URL. Zulip URLs often look like `<name>.zulipchat.com`,
 `zulip.<name>.com`, or `chat.<name>.com` (replace `<name>` with the name of your
  organization).

* Ask your organization administrators for your Zulip URL.

### I signed up with Google/GitHub auth and never set a password

If you signed up using passwordless authentication and want to start logging
in via email/password, you can
[reset your password](/help/change-your-password).

### I forgot my password

You can [reset your password](/help/change-your-password). This requires
access to the email address you currently have on file. We recommend
[keeping your email address up to date](change-your-email-address).
