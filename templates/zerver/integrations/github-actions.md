# Zulip GitHub Actions integration

It's easy to send Zulip messages from GitHub Actions!

{start_tabs}

1. {!create-a-generic-bot.md!}
   Note down the bot's email address and API key.

1. To send Zulip notifications whenever your workflow runs, add the
   `zulip/github-actions-zulip/send-message@v1` action to your GitHub
   Actions workflow file, and set the input values as specified in the
   [README][README] of the [Zulip GitHub Actions repository][repo].

{end_tabs}

### Related documentation

* [Zulip GitHub Actions repository][repo]

* [Configuring the Zulip Send Message Action][README]

* [GitHub integration](/integrations/doc/github)

[README]: https://github.com/zulip/github-actions-zulip/blob/main/send-message/README.md
[repo]: https://github.com/zulip/github-actions-zulip
