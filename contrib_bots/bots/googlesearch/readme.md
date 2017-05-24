# Google Search bot

This bot allows users to do Google search queries and have the bot respond withthe first search result to whatever context it is queried from, whether it's stream or private. It is by default set to the highest safe-search setting.

## Usage

Run this bot as described in [here](http://zulip.readthedocs.io/en/latest/bots-guide.html#how-to-deploy-a-bot).

Use this bot with the following command

`@mentioned-bot <search terms>`

This will convert return the first link found by Google for `<search terms>` and print the resulting URL.

If no `<search terms>` are entered, a help message is printed instead.

If there was an error in the process of running the search (socket errors, Google search function failed, or general failures), an error message is returned.
