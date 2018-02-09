    Next, on your {{ settings_html|safe }},
    [create a bot](/help/add-a-bot-or-integration) for
    {{ integration_display_name }}. Make sure that you select
    **Incoming webhook** as the **Bot type**:

    ![](/static/images/help/bot_types.png)

    The API key for an incoming webhook bot cannot be used to read messages out
    of Zulip. Thus, using an incoming webhook bot lowers the security risk of
    exposing the bot's API key to a third-party service.

    Fill out the rest of the fields, and click **Create bot**.

    Now, construct the URL for the {{ integration_display_name }}
    bot using the bot's API key and the desired stream name:

    {!webhook-url.md!}

    Modify the parameters of the URL above, where `api_key` is the API key
    of your Zulip bot, and `stream` is the stream name you want the
    notifications sent to.
