You are using the **GitHub auth backend**, but it is not properly
configured. Please check the following:

You have added `{{ root_domain_uri }}/complete/github/` as the callback URL
in the OAuth application in GitHub. You can create OAuth apps from
[GitHub's developer site](https://github.com/settings/developers).

* You have set `SOCIAL_AUTH_GITHUB_KEY` in `{{ settings_path }}` and
`social_auth_github_secret` in `{{ secrets_path }}` with the values
from your OAuth application.

* Navigate back to the login page and attempt the GitHub auth flow again.
