You are using the **Google auth backend**, but it is not properly
configured. Please check the following:

* You have created a Google Oauth2 client and enabled the Google+ API.
You can create OAuth2 apps at [the Google developer console](https://console.developers.google.com).

* You have configured your OAuth2 client to allow redirects to your
server's Google auth URL: `{{ root_domain_uri }}/accounts/login/google/done/`.

* You have set `GOOGLE_OAUTH2_CLIENT_ID` in `{{ settings_path }}` and
`google_oauth2_client_secret` in `{{ secrets_path }}`.

* Navigate back to the login page and attempt the Google auth flow again.
