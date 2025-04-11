# Zulip Discourse integration

Forward new Discourse posts to Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. Install the Discourse [Chat Integration][chat-integration].

1. In your **Discourse site settings**, toggle
   `chat_integration_zulip_enabled`, and fill in the following information:

    * `chat_integration_zulip_server`: {{ zulip_url }}
    * `chat_integration_zulip_bot_api_key`: your bot's API key
    * `chat_integration_zulip_bot_email_address`: your bot's email

1. Go to the **Plugins** tab, click on **Chat Integration**. Select
   **Zulip**, and click **Add Channel**.

1. Set **Stream** to the [channel](/help/create-a-channel) name that you'd
   like to receive notifications in, set **Subject** to the topic name, and
   click **Save Channel**.

1. To filter the posts you'd like to forward to Zulip,
   [configure the rules][configuring-rules] in your Discourse forum's
   **Chat Integrations** panel.

{end_tabs}

### Related documentation

- [Discourse Chat Integration][chat-integration]
- [Discourse's documentation on the Zulip integration][setup-instructions]

[setup-instructions]: https://meta.discourse.org/t/68501
[chat-integration]: https://meta.discourse.org/t/discourse-chat-integration/66522
[configuring-rules]: https://meta.discourse.org/t/discourse-chat-integration/66522#configuring-rules-4
