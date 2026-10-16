# Zulip Asyntai integration

Ask questions in Zulip and get answers from your organization's own content!

{start_tabs}

1. [Create an outgoing webhook bot](/help/add-a-bot-or-integration), setting
   **Endpoint URL** to `https://asyntai.com/zulip/webhook/` and leaving
   **Interface** set to **Generic**.

1. Send the new bot a direct message. It will reply with a link to connect
   your Asyntai account.

1. Open that link, sign in to [Asyntai](https://asyntai.com/), and choose
   which website the bot should answer from.

1. [Subscribe the bot][subscribe-channels] to any channels where you would
   like to mention it.

{end_tabs}

You're done! Send the bot a direct message, or mention it in a channel, and
it will answer from your website, uploaded documents, and help center
articles.

### Related documentation

* [Asyntai Zulip integration documentation](https://asyntai.com/documentation/integrations/zulip/)
* [Channel permissions for bots](/help/bots-overview#channel-permissions-for-bots)

[subscribe-channels]: /help/manage-user-channel-subscriptions#subscribe-a-user-to-a-channel
