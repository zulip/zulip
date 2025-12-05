# Google Search bot

This bot allows users to do Google search queries and have the bot
respond with the first search result.  It is by default set to the
highest safe-search setting.

## Usage

Run this bot as described
[here](https://zulipchat.com/api/running-bots#running-a-bot).

Use this bot with the following command

`@mentioned-bot <search terms>`

This will return the first link found by Google for `<search terms>`
and print the resulting URL.

If no `<search terms>` are entered, a help message is printed instead.

If there was an error in the process of running the search (socket
errors, Google search function failed, or general failures), an error
message is returned.
