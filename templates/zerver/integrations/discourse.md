# Zulip Discourse integration

Get notifications for new Discourse posts in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. Install the Discourse [Chat Integration][chat-integration].

1. In your **Discourse site settings**, fill the form with the following:

    * `chat_integration_zulip_server`: {{ zulip_url }}
    * `chat_integration_zulip_bot_api_key`: your [bot][bot]'s API key
    * `chat_integration_zulip_bot_email_address`: your [bot][bot]'s email
    * Enable `chat_integration_zulip_enabled`.

[bot]: ../../#settings/your-bots

1. Go to the **Plugins** tab, click on **Chat Integration**. Select
   **Zulip**, and click **Add Channel**.

1. Set **Stream** to the [channel](/help/create-a-channel) name that you'd
   like to receive notifications in, set **Subject** to the topic name, and
   click **Save Channel**.

{end_tabs}

### Related documentation

- [Discourse Chat Integration][chat-integration]
- [Discourse's documentation on the Zulip integration][setup-instructions]

[setup-instructions]: https://meta.discourse.org/t/68501
[chat-integration]: https://meta.discourse.org/t/discourse-chat-integration/66522
