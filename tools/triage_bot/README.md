# Triage bot

The triage bot posts one message (a "card") for each new issue and PR
in zulip/zulip. The cards go to a private channel on chat.zulip.org,
in one topic per week. A card suggests what to do with the item, and has
a reply that a maintainer can paste.

The bot only reads from GitHub. It never comments, labels, or runs PR
code. Items opened by a maintainer get a one-line card instead,
written without the model. The list of maintainers is `MAINTAINERS` in
`gather.py`.

## Running it locally

You need `GH_TOKEN` set to a GitHub token. With the `gh` CLI,
`GH_TOKEN=$(gh auth token)` works.
To print the card for an item instead of posting it:

```
$ ./tools/triage_bot/triage_bot.py --item 12345 --dry-run
```

To write a card, the bot needs `ANTHROPIC_API_KEY` set. Without it,
you only get cards for maintainer items.

If you also set `ZULIP_TRIAGE_BOT_EMAIL`, `ZULIP_TRIAGE_BOT_API_KEY`
and `ZULIP_TRIAGE_CHANNEL` (a chat.zulip.org bot's email and API key,
and the cards' channel), the dry run checks whether the item already
has a card. If it does, the bot stops and prints no card.
