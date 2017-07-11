Next, on your {{ settings_html|safe }},
[create a bot](/help/add-a-bot-or-integration) for
{{ integration_display_name }}. Make sure that you select
**Incoming webhook** as the **Bot type**:

![](/static/images/help/bot_types.png)

The API keys for "Incoming webhook" bots are limited to only
sending messages via webhooks. Thus, this bot type lessens
the security risks associated with exposing the bot's API
key to third-party services.

Construct the URL for the {{ integration_display_name }}
bot using the bot API key and stream name:

{!webhook-url.md!}

Modify the parameters of the URL above, where `api_key` is the API key
of your Zulip bot, and `stream` is the stream name you want the
notifications sent to.
