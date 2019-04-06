# Authentication in the development environment

This page documents special notes that are useful for configuring
Zulip's various authentication methods for testing in a development
environment.

## Testing OAuth in development

Among the many [authentication methods](../production/authentication-methods.html)
we support, a server can be configured to allow users to sign in with
their Google accounts or GitHub accounts, using the OAuth protocol.

Because these authentication methods involve an interaction between
Zulip, an external service, and the user's browser, and particularly
because browsers can (rightly!) be picky about the identity of sites
you interact with, the preferred way to set them up in a development
environment is to set up the real Google and GitHub to process auth
requests for your development environment.

The steps to do this are a variation of the steps documented in
`prod_settings_template.py`. Here are the full procedures for dev:

### Google

* Visit https://console.developers.google.com and navigate to "APIs &
  services" > "Credentials".  Create a "Project" which will correspond
  to your dev environment.

* Navigate to "APIs & services" > "Library", and find the "Google+
  API".  Choose "Enable".

* Return to "Credentials", and select "Create credentials".  Choose
  "OAuth client ID", and follow prompts to create a consent screen, etc.
  For "Authorized redirect URIs", fill in
  `https://zulipdev.com:9991/accounts/login/google/done/` .

* You should get a client ID and a client secret. Copy them. In
  `dev_settings.py`, set `GOOGLE_OAUTH2_CLIENT_ID` to the client ID,
  and in `dev-secrets.conf`, set `google_oauth2_client_secret` to the
  client secret.

### GitHub

* Register an OAuth2 application with GitHub at one of
  https://github.com/settings/developers or
  https://github.com/organizations/ORGNAME/settings/developers.
  Specify `http://zulipdev.com:9991/complete/github/` as the callback URL.

* You should get a page with settings for your new application,
  showing a client ID and a client secret.  In `dev_settings.py`, set
  `SOCIAL_AUTH_GITHUB_KEY` to the client ID, and in
  `dev-secrets.conf`, set `social_auth_github_secret` to the client secret.

### When SSL is required

Some OAuth providers (such as Facebook) require HTTPS on the callback
URL they post back to, which isn't supported directly by the Zulip
development environment.  If you run a
[remote Zulip development server](../development/remote.html), we have
instructions for
[an nginx reverse proxy with SSL](../development/remote.html#using-an-nginx-reverse-proxy)
that you can use for your development efforts.

## Testing LDAP in development

Historically, one of the more common classes of bug reports with
Zulip's authentication was users having trouble getting LDAP
authentication working.  A big part of the cause was because setting
up a local LDAP server for development was difficult.

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
