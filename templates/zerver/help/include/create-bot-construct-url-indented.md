    {!create-a-bot-indented.md!}

    Construct the URL for the {{ integration_display_name }}
    bot using the bot's API key and the desired stream name:

    {!webhook-url.md!}

    Modify the parameters of the URL above, where `api_key` is the API key
    of your Zulip bot, and `stream` is the stream name you want the
    notifications sent to. If you do not specify a `stream`, the bot will
    send notifications via PMs to the creator of the bot.

    To change the topic used by the bot, simply append `&topic=name`
    to the end of the above URL, where `name` is your topic.
