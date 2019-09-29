# Authentication in the development environment

This page documents special notes that are useful for configuring
Zulip's various authentication methods for testing in a development
environment.

## Testing OAuth in development

Among the many [authentication methods](../production/authentication-methods.md)
we support, a server can be configured to allow users to sign in with
their Google accounts or GitHub accounts, using the OAuth protocol.

Because these authentication methods involve an interaction between
Zulip, an external service, and the user's browser, and particularly
because browsers can (rightly!) be picky about the identity of sites
you interact with, the preferred way to set them up in a development
environment is to set up the real Google and GitHub to process auth
requests for your development environment.

The steps to do this are a variation of the steps documented in
`prod_settings_template.py`.  The main differences here are driven by
the fact that `dev_settings.py` is in Git, so it can be inconvenient
to put secrets there.  In development, we allow providing those values
in the untracked file `zproject/dev-secrets.conf`, using the standard
lower-case naming convention for that file.

Here are the full procedures for dev:

### Google

* Visit https://console.developers.google.com and navigate to "APIs &
  services" > "Credentials".  Create a "Project" which will correspond
  to your dev environment.

* Navigate to "APIs & services" > "Library", and find the "Identity
  Toolkit API".  Choose "Enable".

* Return to "Credentials", and select "Create credentials".  Choose
  "OAuth client ID", and follow prompts to create a consent screen, etc.
  For "Authorized redirect URIs", fill in
  `http://zulipdev.com:9991/complete/google/` .

* You should get a client ID and a client secret. Copy them. In
  `dev-secrets.conf`, set `social_auth_google_key` to the client ID
  and `social_auth_google_secret` to the client secret.

### GitHub

* Register an OAuth2 application with GitHub at one of
  https://github.com/settings/developers or
  https://github.com/organizations/ORGNAME/settings/developers.
  Specify `http://zulipdev.com:9991/complete/github/` as the callback URL.

* You should get a page with settings for your new application,
  showing a client ID and a client secret.  In `dev-secrets.conf`, set
  `social_auth_github_key` to the client ID and `social_auth_github_secret`
  to the client secret.

### SAML

* Register a SAML authentication with Okta at
  https://zulipchat-admin.okta.com/admin/apps/saml-wizard/create.  Specify:
    * `http://localhost:9991/complete/saml/` for the "Single sign on URL"`.
    * `http://localhost:9991` for the "Audience URI (SP Entity ID)".
    * Skip "Default RelayState".
    * Skip "Name ID format".
    * Set 'Email` for "Application username format".
    * Provide "Attribute statements" of `email` to `user.email`,
      `first_name` to `user.firstName`, and `last_name` to `user.lastName`.
* Assign at least one account to the in the "Assignments" tab.  Uou'll
  be logging in using this email address in the development
  environment (so make sure that email has an account and can login
  to the target realm).
* Visit the big "Setup instructions" button on the "Sign on" tab.
* Edit `zproject/dev-secrets.conf` to add the two values provided:
    * Set `saml_url = http...` from "Identity Provider Single Sign-On
      URL".
    * Set `saml_entity_id = http://...` from "Identity Provider Issuer".
    * Download the certificate and put it at the path `zproject/dev_saml.cert`.
* Now you should have working SAML authentication!

### When SSL is required

Some OAuth providers (such as Facebook) require HTTPS on the callback
URL they post back to, which isn't supported directly by the Zulip
development environment.  If you run a
[remote Zulip development server](../development/remote.md), we have
instructions for
[an nginx reverse proxy with SSL](../development/remote.html#using-an-nginx-reverse-proxy)
that you can use for your development efforts.

## Testing LDAP in development

Before Zulip 2.0, one of the more common classes of bug reports with
Zulip's authentication was users having trouble getting [LDAP
authentication](../production/authentication-methods.html#ldap-including-active-directory)
working.  The root cause was because setting up a local LDAP server
for development was difficult, which meant most developers were unable
to work on fixing even simple issues with it.

We solved this problem for our unit tests long ago by using the
popular [fakeldap](https://github.com/zulip/fakeldap) library.  And in
2018, we added convenient support for using fakeldap in the Zulip
development environment as well, so that you can go through all the
actual flows for LDAP configuration.

- To enable fakeldap, set `FAKE_LDAP_MODE` in
`zproject/dev_settings.py` to one of the following options.  For more
information on these modes, refer to
[our production docs](../production/authentication-methods.html#ldap-including-active-directory):
  - `a`: If users' email addresses are in LDAP and used as username.
  - `b`: If LDAP only has usernames but email addresses are of the form
  username@example.com
  - `c`: If LDAP usernames are completely unrelated to email addresses.

- To disable fakeldap, set `FAKE_LDAP_MODE` back to `None`.

- In all fakeldap configurations, users' fake LDAP passwords are equal
  to their usernames (e.g. for `ldapuser1@zulip.com`, the password is
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
`zproject/dev_settings.py` to sync several of those fields.  For
example:

* Modes `a` and `b` will set the user's avatar on account creation and
  update it when `manage.py sync_ldap_user_data` is run.
* Mode `b` is configured to automatically have the `birthday` and
  `Phone number` custom profile fields populated/synced.
* Mode `a` is configured to deactivate/reactivate users whose accounts
  are disabled in LDAP when `manage.py sync_ldap_user_data` is run.
  (Note that you'll likely need to edit
  `zerver/lib/dev_ldap_directory.py` to ensure there are some accounts
  configured to be disabled).

### Automated testing

For our automated tests, we generally configure custom LDAP data for
each individual test, because that generally means one can understand
exactly what data is being used in the test without looking at other
resources.  It also gives us more freedom to edit the development
environment directory without worrying about tests.

## Two Factor Authentication

Zulip uses [django-two-factor-auth][0] as a beta 2FA integration.

To enable 2FA, set `TWO_FACTOR_AUTHENTICATION_ENABLED` in settings to
`True`, then log into Zulip and add otp device from settings
page. Once the device is added, password based authentication will ask
for one-time-password.  In the development environment., this
one-time-password will be printed to the console when you try to
login.  Just copy-paste it into the form field to continue.

Direct development logins don't prompt for 2FA one-time-passwords, so
to test 2FA in development, make sure that you login using a
password.  You can get the passwords for the default test users using
`./manage.py print_initial_password`.

[0]: https://github.com/Bouke/django-two-factor-auth
