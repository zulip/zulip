# Zulip Discourse integration

Get Discourse notifications in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. Install the Discourse [Chat Integration][chat-integration].

1. In your **Discourse site settings**, set the following properties.

    * Set `chat_integration_zulip_server` to your Zulip hostname, e.g.,
      `https://your_organization.zulipchat.com`.
    * Set `chat_integration_zulip_bot_api_key` to your Zulip bot's
      [API key](api-key).
    * Set `chat_integration_zulip_bot_email_address` to your Zulip bot's
      email address.
    * Enable `chat_integration_zulip_enabled`.

1. Go to the **Plugins** tab, click on **Chat Integration**. Select
   **Zulip**, and click **Add Channel**.

1. Set **Stream** to the [channel](/help/create-a-channel) name that you'd
   like to receive notifications in, set **Subject** to the topic name, and
   click **Save Channel**.

{end_tabs}

{!congrats.md!}

![Discourse chat integration](/static/images/integrations/discourse/001.png)

### Related documentation

- [Discourse Chat Integration][chat-integration]
- [Discourse's documentation on the Zulip integration][setup-instructions]

[setup-instructions]: https://meta.discourse.org/t/68501
[chat-integration]: https://meta.discourse.org/t/discourse-chat-integration/66522
[api-key]: https://zulip.com/api/api-keys#get-a-bots-api-key
