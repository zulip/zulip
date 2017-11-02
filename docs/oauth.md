# Google & GitHub authentication with OAuth 2

Among the many [authentication methods](prod-authentication-methods.html)
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

* Visit https://console.developers.google.com, click on Credentials on
the left sidebar and create a Oauth2 client ID that allows redirects
to `https://localhost:9991/accounts/login/google/done/`.

* Go to the Library (left sidebar), then under "Social APIs" click on
"Google+ API" and click the button to enable the API.

* Uncomment `'zproject.backends.GoogleMobileOauth2Backend'` in
`AUTHENTICATION_BACKENDS` in `dev_settings.py`.

* Uncomment `GOOGLE_OAUTH2_CLIENT_ID` in `prod_settings_template.py` &
assign it the Client ID you got from Google.

* Put the Client Secret you got from Google as
`google_oauth2_client_secret` in `dev-secrets.conf`.

### GitHub

* Register an OAuth2 application with GitHub at one of
https://github.com/settings/developers or
https://github.com/organizations/ORGNAME/settings/developers.
Specify `http://localhost:9991/complete/github/` as the callback URL.

* Uncomment `'zproject.backends.GitHubAuthBackend'` in
`AUTHENTICATION_BACKENDS` in `dev_settings.py`.

* Uncomment `SOCIAL_AUTH_GITHUB_KEY` in `prod_settings_template.py` &
assign it the Client ID you got from GitHub.

* Put the Client Secret you got from GitHub as
`social_auth_github_secret` in `dev-secrets.conf`.
