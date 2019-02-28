# About bots

Bots allow you to

* Send content into and out of Zulip.
* Send content to and from another product.
* Automate tasks a human user could do.

A bot that sends content to or from another product is often called an
**integration**.

### Pre-made bots

Zulip natively supports integrations with over 90 products, and with
hundreds more through Zapier and IFTTT. If you're looking to add an
integration with an existing product, see our
[list of integrations](/integrations), along with those of
[Zapier](https://zapier.com/apps) and [IFTTT](https://ifttt.com/search).

## Anatomy of a bot

You can think of a bot as a special kind of user, with limited permissions.
Each bot has a **name**, **avatar**, **email**, **bot type** and **API key**.

* The **name** and **avatar** play the same role they do for human users. They
are the most visible attributes of a bot.

* The **email** is not used for anything, and will likely be removed in a
future version of Zulip.

* The **bot type** determines what the bot can and can't do (see below).

* The **API key** is how the bot identifies itself to Zulip. Anyone with the
  bot's API key can impersonate the bot.

## Bot type

The **bot type** determines what the bot can do.

Bot type | Permissions | Common uses
---|---|---
Incoming webhook | Send messages into Zulip | Third party integrations
Outgoing webhook | Send messages into Zulip, read messages where the bot is addressed | Third party integrations, most custom bots <!-- # ignorelongline -->
Generic | Anything the bot creator can do | Automating tasks, bots that listen to all messages on a stream
API super bot (self-hosted only) | Anything any user can do | Mirroring

It's generally best to pick the most restricted bot type that is sufficient
to do the task at hand. Anyone with the bot's API key can do anything the
bot can.

A few more details:

* **Outgoing webhook**: The bot can read private messages where the bot is a
  participant, and stream messages where the bot is [mentioned](/help/mention-a-user-or-group). When the
  bot is PM'd or mentioned, it POSTs the message content to a URL of your
  choice. The POST request format can be in a Zulip format or a
  Slack-compatible format.

    This is the preferred bot type for interactive bots built on top of Zulip
    botserver.

* **Generic**: Note that if you truly want to impersonate yourself
  (e.g. write messages that come from you, rather than from a look-a-like),
  you'll need to use your **personal API key**.

* **API super bot**: You cannot create this from the web interface. Contact
  `support@zulipchat.com` if you'd like information on how to set this up.

## Adding bots

By default, anyone other than guests can [add a bot](/help/add-a-bot-or-integration) to a
Zulip organization, but administrators can
[restrict bot creation](/help/restrict-bot-creation). Any bot that is added
is visible and available for anyone to use.
