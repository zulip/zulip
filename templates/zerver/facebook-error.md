You are attempting to use the **Facebook auth backend**, but it is not
properly configured. To configure, please check the following:

1. You have registered an App at <https://developer.facebook.com>, and
    1. Added the 'Facebook Login' product,
    2. In the 'Facebook Login' settings:
        1. Ensured 'Client OAuth Login' is enabled,
        2. Ensured 'Web OAuth Login' is enabled,
        3. Added `{{ root_domain_url }}/complete/facebook` to the 'Valid OAuth Redirect URIs'.
2. You have set `SOCIAL_AUTH_FACEBOOK_KEY` in `{{ settings_path }}` and
`social_auth_facebook_secret` in `{{ secrets_path }}` with your Facebook App's App ID and App Secret, respectively.

Once you have checked this, navigate back to the login page and attempt the Facebook auth flow again.
