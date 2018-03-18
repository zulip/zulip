{!create-a-bot.md!}

Construct the URL for the {{ integration_display_name }}
bot using the bot's API key and the desired stream name:

{!webhook-url.md!}

Modify the parameters of the URL above, where `api_key` is the API key
of your Zulip bot, and `stream` is the stream name you want the
notifications sent to. If you do not specify a `stream`, the bot will
send notifications via PMs to the creator of the bot.

If you'd like this integration to always send to the topic
`your_topic`, just add `&topic=your_topic` to the end of the URL.
