You are attempting to use the **GitLab auth backend**, but it is not
properly configured. To configure, please check the following:

* You have added `{{ root_domain_uri }}/complete/gitlab/` as the callback
URL in the OAuth application in GitLab. You can register OAuth apps at
[GitLab Applications](https://gitlab.com/profile/applications).

* You have set `{{ client_id_key_name }}` in `{{ settings_path }}` and
`social_auth_gitlab_secret` in `{{ secrets_path }}` with the values
from your OAuth application.

* Navigate back to the login page and attempt the GitLab auth flow again.
