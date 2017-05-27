# Overview

This is the documentation for how to set up and run the GitHub comment bot. (`git_hub_comment.py`)

This directory contains library code for running Zulip
bots that react to messages sent by users.

This bot will allow you to comment on a GitHub issue.
You should preface messages with `@comment` or `@gcomment`.
You will need to have a GitHub account, and a GitHub OAuth token.

## Setup
Before running this bot, make sure to get a GitHub OAuth token.
You can look at this tutorial if you need help:
<https://help.github.com/articles/creating-an-access-token-for-command-line-use/>
The token will need to be authorized for the following scopes: `gist, public_repo, user`.
Store it in the `~/github-auth.conf` file, along with your username, in the format:
github_repo = <repo_name>  (The name of the repo to post to)
github_repo_owner = <repo_owner>  (The owner of the repo to post to)
github_username = <username>  (The username of the GitHub bot)
github_token = <oauth_token>   (The personal access token for the GitHub bot)
`<repository_owner>/<repository>/<issue_number>/<your_comment`.

## Running the bot

Here is an example of running the `git_hub_comment` bot from
inside a Zulip repo:

    `cd ~/zulip/api`
    `bots_api/run.py bots/git_hub_comment/git_hub_comment.py --config-file ~/.zuliprc-prod`

Once the bot code starts running, you will see a
message explaining how to use the bot, as well as
some log messages.  You can use the `--quiet` option
to suppress some of the informational messages.

The bot code will run continuously until you kill them with
control-C (or otherwise).

### Configuration

For this document we assume you have some prior experience
with using the Zulip API, but here is a quick review of
what a `.zuliprc` files looks like.  You can connect to the
API as your own human user, or you can go into the Zulip settings
page to create a user-owned bot.

    [api]
    email=someuser@example.com
    key=<your api key>
    site=https://zulip.somewhere.com


