# Zulip Atolio integration

Index Zulip channels, topics, and messages in your Atolio knowledge base!

{start_tabs}

1. {!create-a-generic-bot.md!}

1. [Subscribe the bot][subscribe-channels] to the Zulip channels that you
   want Atolio to index.

1. [Download the `zuliprc` file](/help/manage-a-bot#download-zuliprc-configuration-file)
   for the bot you created above.

1. In Atolio, configure the Zulip connector using the following values
   from the `zuliprc` file:

    * **Domain**: Your Zulip organization URL.
    * **Email**: The bot's email address.
    * **Token**: The bot's API key.

1. Use the Atolio connector configuration to include or exclude specific
   topics at the [`topic` resource level][content-filtering] using the
   "channel name/topic name" format.

{end_tabs}

You're done! You should be able to index Zulip from Atolio.

### Related documentation

* [Atolio Zulip Connector documentation](https://docs.atolio.com/configure-sources/zulip/)
* [Channel permissions for bots](/help/bots-overview#channel-permissions-for-bots)

[subscribe-channels]: /help/manage-user-channel-subscriptions#subscribe-a-user-to-a-channel
[content-filtering]: https://docs.atolio.com/configure-sources/zulip/#:~:text=bot%20or%20user-,Content%20Filtering,-The%20Zulip%20connector
