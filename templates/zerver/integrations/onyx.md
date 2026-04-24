# Zulip Onyx Integration

Export discussions from Zulip channels and topics to your Onyx knowledge
base!

{start_tabs}

1. {!create-a-generic-bot.md!}

1. [Subscribe the bot][subscribe-channels] to the Zulip channels that you
   want to export.

1. [Download the `zuliprc` file](/help/manage-a-bot#download-zuliprc-configuration-file)
   for the bot you created above.

1. In Onyx, open the **Admin Dashboard** and select the **Zulip Connector**.

1. Under **Provide Credentials**, paste the bot's **email address** and
   **API key** from the `zuliprc` file you downloaded above. Click
   **Update**.

1. Set **Realm name** to the name of your Zulip organization, set
   **Realm URL** to `{{ zulip_url }}`, and click **Connect**.

{end_tabs}

You're done! You should be able to index Zulip from your Onyx **Connectors
Dashboard**!

### Related documentation

* [Zulip Connector documentation](https://docs.onyx.app/admins/connectors/official/zulip)
* [About Onyx Connectors](https://docs.onyx.app/admins/connectors/overview)

[subscribe-channels]: /help/manage-user-channel-subscriptions#subscribe-a-user-to-a-channel
