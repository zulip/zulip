You are using the **Apple auth backend**, but it is not
properly configured. Please check the following:

* You have registered `{{ root_domain_uri }}/complete/apple/`
  as the callback URL for your Services ID in Apple's developer console. You can
  enable "Sign in with Apple" for an app at
  [Certificates, Identifiers & Profiles](https://developer.apple.com/account/resources/).

* You have set `SOCIAL_AUTH_APPLE_SERVICES_ID`,
  `SOCIAL_AUTH_APPLE_APP_ID`, `SOCIAL_AUTH_APPLE_TEAM`,
  and `SOCIAL_AUTH_APPLE_KEY` in `{{
  settings_path }}` and stored the private key provided by Apple at
  `/etc/zulip/apple-auth-key.p8` on the Zulip server, with
  proper permissions set.

* Navigate back to the login page and attempt the "Sign in with Apple"
  flow again.
