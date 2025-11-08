# Authentication in the development environment

This page documents special notes that are useful for configuring
Zulip's various [authentication
methods](../production/authentication-methods.md) for testing in a
development environment.

Many of these authentication methods involve a complex interaction
between Zulip, an external service, and the user's browser. Because
browsers can (rightly!) be picky about the identity of sites you
interact with, the preferred way to set up authentication methods in a
development environment is provide secret keys so that you can go
through the real flow.

The steps to do this are a variation of the steps discussed in the
production documentation, including the comments in
`zproject/prod_settings_template.py`. The differences here are driven
by the fact that `dev_settings.py` is in Git, so it is inconvenient
for local [settings configuration](../subsystems/settings.md). As a
result, in the development environment, we allow setting certain
settings in the untracked file `zproject/dev-secrets.conf` (which is
also serves as `/etc/zulip/zulip-secrets.conf`).

Below, we document the procedure for each of the major authentication
methods supported by Zulip.

### Email and password

Zulip's default EmailAuthBackend authenticates users by verifying
control over their email address, and then allowing them to set a
password for their account. There are two development environment
details worth understanding:

- All of our authentication flows in the development environment have
  special links to the `/emails` page (advertised in `/devtools`),
  which shows all emails that the Zulip server has "sent" (emails are
  not actually sent by the development environment), to make it
  convenient to click through the UI of signup, password reset, etc.
- There's a management command,
  `manage.py print_initial_password username@example.com`, that prints
  out **default** passwords for the development environment users.
  Note that if you change a user's password in the development
  environment, those passwords will no longer work. It also prints
  out the user's **current** API key.

### Google

- Visit [the Google developer
  console](https://console.developers.google.com) and navigate to "APIs
  & services" > "Credentials". Create a "Project", which will correspond
  to your dev environment.

- Navigate to "APIs & services" > "Library", and find the "Identity
  Toolkit API". Choose "Enable".

- Return to "Credentials", and select "Create credentials". Choose
  "OAuth client ID", and follow prompts to create a consent screen, etc.
  For "Authorized redirect URIs", fill in
  `http://auth.zulipdev.com:9991/complete/google/` .

- You should get a client ID and a client secret. Copy them. In
  `dev-secrets.conf`, set `social_auth_google_key` to the client ID
  and `social_auth_google_secret` to the client secret.

### GitHub

- Register an OAuth2 application with GitHub at one of
  <https://github.com/settings/developers> or
  `https://github.com/organizations/<your-org>/settings/applications`.
  Specify `http://auth.zulipdev.com:9991/complete/github/` as the callback URL.

- You should get a page with settings for your new application,
  showing a client ID and a client secret. In `dev-secrets.conf`, set
  `social_auth_github_key` to the client ID and `social_auth_github_secret`
  to the client secret.

### GitLab

- Register an OAuth application with GitLab at
  <https://gitlab.com/oauth/applications>.
  Specify `http://auth.zulipdev.com:9991/complete/gitlab/` as the callback URL.

- You should get a page containing the Application ID and Secret for
  your new application. In `dev-secrets.conf`, enter the Application
  ID as `social_auth_gitlab_key` and the Secret as
  `social_auth_gitlab_secret`.

### Apple

- Visit <https://developer.apple.com/account/resources/>,
  Enable App ID and Create a Services ID with the instructions in
  <https://help.apple.com/developer-account/?lang=en#/dev1c0e25352> .
  When prompted for a "Return URL", enter
  `http://auth.zulipdev.com:9991/complete/apple/` .

- [Create a Sign in with Apple private key](https://help.apple.com/developer-account/?lang=en#/dev77c875b7e)

- In `dev-secrets.conf`, set
  - `social_auth_apple_services_id` to your
    "Services ID" (eg. com.application.your).
  - `social_auth_apple_app_id` to "App ID" or "Bundle ID".
    This is only required if you are testing Apple auth on iOS.
  - `social_auth_apple_key` to your "Key ID".
  - `social_auth_apple_team` to your "Team ID".
- Put the private key file you got from apple at the path
  `zproject/dev_apple.key`.

### SAML

- Sign up for a [developer Okta account](https://developer.okta.com/).
- Set up SAML authentication by following
  [Okta's documentation](https://developer.okta.com/docs/guides/saml-application-setup/overview/).
  Specify:
  - `http://localhost:9991/complete/saml/` for the "Single sign on URL"`.
  - `http://localhost:9991` for the "Audience URI (SP Entity ID)".
  - Skip "Default RelayState".
  - Skip "Name ID format".
  - Set 'Email` for "Application username format".
  - Provide "Attribute statements" of `email` to `user.email`,
    `first_name` to `user.firstName`, and `last_name` to `user.lastName`.
- Assign at least one account in the "Assignments" tab. You'll use it for
  signing up / logging in to Zulip.
- Visit the big "Setup instructions" button on the "Sign on" tab.
- Edit `zproject/dev-secrets.conf` to add the two values provided:
  - Set `saml_url = http...` from "Identity Provider Single Sign-On
    URL".
  - Set `saml_entity_id = http://...` from "Identity Provider Issuer".
  - Download the certificate and put it at the path `zproject/dev_saml.cert`.
- Now you should have working SAML authentication!
- You can sign up to the target realm with the account that you've "assigned"
  in the previous steps (if the account's email address is allowed in the realm,
  so you may have to change the realm settings to allow the appropriate email domain)
  and then you'll be able to log in freely. Alternatively, you can create an account
  with the email in any other way, and then just use SAML to log in.

### When SSL is required

Some OAuth providers (such as Facebook) require HTTPS on the callback
URL they post back to, which isn't supported directly by the Zulip
development environment. If you run a
[remote Zulip development server](remote.md), we have
instructions for
[an nginx reverse proxy with SSL](remote.md#using-an-nginx-reverse-proxy)
that you can use for your development efforts.

## Testing LDAP in development

Before Zulip 2.0, one of the more common classes of bug reports with
Zulip's authentication was users having trouble getting [LDAP
authentication](../production/authentication-methods.md#ldap-including-active-directory)
working. The root cause was because setting up a local LDAP server
for development was difficult, which meant most developers were unable
to work on fixing even simple issues with it.

We solved this problem for our unit tests long ago by using the
popular [fakeldap](https://github.com/zulip/fakeldap) library. And in
2018, we added convenient support for using fakeldap in the Zulip
development environment as well, so that you can go through all the
actual flows for LDAP configuration.

- To enable fakeldap, set `FAKE_LDAP_MODE` in
  `zproject/dev_settings.py` to one of the following options. For more
  information on these modes, refer to
  [our production docs](../production/authentication-methods.md#ldap-including-active-directory):

  - `a`: If users' email addresses are in LDAP and used as username.
  - `b`: If LDAP only has usernames but email addresses are of the form
    username@example.com
  - `c`: If LDAP usernames are completely unrelated to email addresses.

- To disable fakeldap, set `FAKE_LDAP_MODE` back to `None`.

- In all fakeldap configurations, users' fake LDAP passwords are equal
  to their usernames (e.g., for `ldapuser1@zulip.com`, the password is
  `ldapuser1`).

- `FAKE_LDAP_NUM_USERS` in `zproject/dev_settings.py` can be used to
  specify the number of LDAP users to be added. The default value for
  the number of LDAP users is 8.

### Testing avatar and custom profile field synchronization

The fakeldap LDAP directories we use in the development environment
are generated by the code in `zerver/lib/dev_ldap_directory.py`, and
contain data one might want to sync, including avatars and custom
profile fields.

We also have configured `AUTH_LDAP_USER_ATTR_MAP` in
`zproject/dev_settings.py` to sync several of those fields. For
example:

- Modes `a` and `b` will set the user's avatar on account creation and
  update it when `manage.py sync_ldap_user_data` is run.
- Mode `b` is configured to automatically have the `birthday` and
  `Phone number` custom profile fields populated/synced.
- Mode `a` is configured to deactivate/reactivate users whose accounts
  are disabled in LDAP when `manage.py sync_ldap_user_data` is run.
  (Note that you'll likely need to edit
  `zerver/lib/dev_ldap_directory.py` to ensure there are some accounts
  configured to be disabled).

### Automated testing

For our automated tests, we generally configure custom LDAP data for
each individual test, because that generally means one can understand
exactly what data is being used in the test without looking at other
resources. It also gives us more freedom to edit the development
environment directory without worrying about tests.

## Two factor authentication

Zulip uses [django-two-factor-auth][0] as a beta 2FA integration.

To enable 2FA, set `TWO_FACTOR_AUTHENTICATION_ENABLED` in settings to
`True`, then log in to Zulip and add an OTP device from the settings
page. Once the device is added, password based authentication will ask
for a one-time-password. In the development environment, this
one-time-password will be printed to the console when you try to
log in. Just copy-paste it into the form field to continue.

Direct development logins don't prompt for 2FA one-time-passwords, so
to test 2FA in development, make sure that you log in using a
password. You can get the passwords for the default test users using
`./manage.py print_initial_password`.

## Password form implementation

By default, Zulip uses `autocomplete=off` for password fields where we
enter the current password, and `autocomplete="new-password"` for
password fields where we create a new account or change the existing
password. This prevents the browser from auto-filling the existing
password.

Visit <https://developer.mozilla.org/en-US/docs/Web/HTML/Attributes/autocomplete> for more details.

[0]: https://github.com/Bouke/django-two-factor-auth
