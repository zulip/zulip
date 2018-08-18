# Google & GitHub authentication with OAuth 2

Among the many [authentication methods](../production/authentication-methods.html)
we support, a server can be configured to allow users to sign in with
their Google accounts or GitHub accounts, using the OAuth protocol.

## Testing OAuth in development

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
