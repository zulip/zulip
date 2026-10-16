# Triage bot

The triage bot posts one message (a "card") for each new issue and PR
in zulip/zulip. The cards go to a private channel on chat.zulip.org,
one topic per item. A card suggests what to do with the item, and has
a reply that a maintainer can paste.

The bot only reads from GitHub. It never comments, labels, or runs PR
code. Items opened by a maintainer get a one-line card instead,
written without the model. The list of maintainers is `MAINTAINERS` in
`gather.py`.

## Running it locally

You need the `gh` CLI, logged in to GitHub or with `GH_TOKEN` set.
To print the card for an item instead of posting it:

```
$ python3 tools/triage_bot/triage_bot.py --item 12345 --dry-run
```

To write a card, the bot needs `ANTHROPIC_API_KEY` set. Without it,
you only get cards for maintainer items.

If you also set the three `ZULIP_TRIAGE_*` settings, the dry run
checks whether the item already has a card. If it does, the bot
stops and prints no card.
