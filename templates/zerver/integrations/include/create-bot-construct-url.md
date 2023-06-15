{!create-an-incoming-webhook.md!}

Construct the URL for the {{ integration_display_name }}
bot using the bot's API key and the desired stream name:

{!webhook-url.md!}

Modify the parameters of the URL above, where `api_key` is the API key
of your Zulip bot, and `stream` is the [URL-encoded][url-encoder]
stream name you want the notifications sent to. If you don't specify a
`stream`, the bot will send notifications via direct messages to the
creator of the bot.

If you'd like this integration to always send notifications to a
specific topic in the specified stream, just include the
[URL-encoded][url-encoder] topic as an additional parameter. E.g.,
for `your topic`, append `&topic=your%20topic` to the URL.

{% if all_event_types is defined %}

{!event-filtering-instruction.md!}

{% endif %}

[url-encoder]: https://www.urlencoder.org/
