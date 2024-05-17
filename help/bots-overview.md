# Bots overview

Bots allow you to

* Send content into and out of Zulip.
* Send content to and from another product.
* Automate tasks a human user could do.

A bot that sends content to or from another product is often called an
[integration](/help/integrations-overview).

## Pre-made bots

Zulip natively supports integrations with over one hundred products, and with
almost a thousand more through Zapier and IFTTT. If you're looking to add an
integration with an existing product, see our
[list of integrations](/integrations/), along with those of
[Zapier](https://zapier.com/apps) and [IFTTT](https://ifttt.com/search).

## Anatomy of a bot

You can think of a bot as a special kind of user, with limited permissions.
Each bot has a **name**, **profile picture**, **email**, **bot type** and **API key**.

* The **name** and **profile picture** play the same role they do for human users. They
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
Generic | Like a normal user account | Automating tasks, bots that listen to all messages on a channel
Incoming webhook | Limited to only sending messages into Zulip | Automated notifications into Zulip
Outgoing webhook | Generic bot that also receives new messages via HTTP post requests | Third party integrations, most custom bots

It's generally best to pick the most restricted bot type that is sufficient
to do the task at hand. Anyone with the bot's API key can do anything the
bot can.

A few more details:

* Bots can send messages to any channel that their owner can,
  inheriting their owner's [sending permissions](/help/channel-posting-policy).

* Bots can be subscribed to channels, and their role can be modified if
  they need to have permission to do administrative actions.

* [Channel permissions](/help/channel-permissions) are the same for bots
  as for other users. Therefore, for private channels with protected
  history, a bot can only access messages sent after it subscribed
  to the channel.

* **Generic**: A generic bot is like a normal Zulip user account that
  cannot log in via a browser.  Note that if you truly want to
  impersonate yourself (e.g. write messages that come from your Zulip
  account), you'll need to use your **personal API key**.

* **Outgoing webhook**: The bot can read direct messages where the bot is a
  participant, and channel messages where the bot is [mentioned](/help/mention-a-user-or-group). When the
  bot is DM'd or mentioned, it POSTs the message content to a URL of your
  choice. The POST request format can be in a Zulip format or a
  Slack-compatible format.

    This is the preferred bot type for interactive bots built on top of Zulip
    Botserver.

## Adding bots

By default, anyone other than guests can [add a bot](/help/add-a-bot-or-integration) to a
Zulip organization, but administrators can
[restrict bot creation](/help/restrict-bot-creation). Any bot that is added
is visible and available for anyone to use.

## Related articles

* [Integrations overview](/help/integrations-overview)
* [Add a bot or integration](/help/add-a-bot-or-integration)
* [Edit a bot](/help/edit-a-bot)
* [Request an integration](/help/request-an-integration)
* [Deactivate or reactivate a bot](/help/deactivate-or-reactivate-a-bot)
* [Restrict bot creation](/help/restrict-bot-creation)
* [View all bots in your organization](/help/view-all-bots-in-your-organization)
* [Generate URL for an integration](/help/generate-integration-url)
