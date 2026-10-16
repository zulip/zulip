# Triage bot

The triage bot posts one message (a "card") for each new issue and PR
in zulip/zulip. The cards go to a private channel on chat.zulip.org,
in one topic per week. A card suggests what to do with the item, and has
a reply that a maintainer can paste.

The bot only reads from GitHub. It never comments, labels, or runs PR
code. Items opened by a maintainer get a one-line card instead,
written without the model. The list of maintainers is `MAINTAINERS` in
`gather.py`.

The bot runs from `.github/workflows/triage-bot.yml`, only in the
zulip/zulip repository. A PR's card waits for its first Zulip CI run,
so that the card can say whether CI passed. Draft PRs get a card when
they are marked ready for review.

## One-time setup

1. On chat.zulip.org, create a generic bot. Note its email and API
   key.
2. Create a private channel for the cards, and subscribe the bot to
   it.
3. In the GitHub repository settings, open **Secrets and
   variables** and then **Actions**. Add these secrets:
   - `ZULIP_TRIAGE_BOT_API_KEY`: the bot's API key.
   - `ANTHROPIC_API_KEY`: an Anthropic API key.
4. On the same page, add these variables:
   - `ZULIP_TRIAGE_BOT_EMAIL`: the bot's email.
   - `ZULIP_TRIAGE_CHANNEL`: the name of the channel.

If the Zulip settings are missing, the workflow posts nothing. If
`ANTHROPIC_API_KEY` is missing, it only posts maintainer cards.

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
