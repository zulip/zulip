# GitHub link previews

Zulip shows a hover preview — the title, author, and state — for links to
[GitHub](https://github.com) issues and pull requests in the message feed.
Previews of **public** repositories work with no server configuration.

## Raising the GitHub API rate limit

Zulip fetches preview data from GitHub's REST API. Without a token,
[GitHub limits][github-rate-limit] the server to 60 requests per hour, shared
across all users, which is too low for most organizations. Configuring a token
raises this limit to 5000 requests per hour.

The token is used only to authenticate to GitHub's API; it does **not** need
access to any repository. Previews are shown to everyone who can read a message,
including guests and logged-out visitors in web-public channels, so the token
should **not** be granted access to private repositories — doing so would expose
private issue and pull request data to those users.

1. Following GitHub's documentation, create a [fine-grained personal access
   token][github-token]. Leave the repository access as **Public repositories**,
   and do not add any account or repository permissions; the token only needs to
   authenticate.

1. Add it to `/etc/zulip/zulip-secrets.conf`, in the `[secrets]` section:

   ```
   github_api_auth_token = <your token>
   ```

1. Restart the Zulip server with
   `/home/zulip/deployments/current/scripts/restart-server`.

[github-rate-limit]: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
[github-token]: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
