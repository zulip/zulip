    On your {{ settings_html|safe }},
    [create a bot](/help/add-a-bot-or-integration) for
    {{ integration_display_name }}. Make sure that you select
    **Incoming webhook** as the **Bot type**:

    ![](/static/images/help/bot_types.png)

    The API key for an incoming webhook bot cannot be used to read messages out
    of Zulip. Thus, using an incoming webhook bot lowers the security risk of
    exposing the bot's API key to a third-party service.

    Fill out the rest of the fields, and click **Create bot**.
