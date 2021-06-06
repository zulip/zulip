You are attempting to use the **Google auth backend**, but it is not
properly configured. To configure, please check the following:

* You have created a Google OAuth2 client and enabled the Identity Toolkit API.
You can create OAuth2 apps at [the Google developer console](https://console.developers.google.com).

* You have configured your OAuth2 client to allow redirects to your
server's Google auth URL: `{{ root_domain_uri }}/complete/google/`.

* You have set `{{ client_id_key_name }}` in `{{ settings_path }}` and
`social_auth_google_secret` in `{{ secrets_path }}`.

* Navigate back to the login page and attempt the Google auth flow again.
