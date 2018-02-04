Get Beeminder notifications in Zulip whenever you're going to derail from your goal!

{!create-stream.md!}

Next, on your {{ settings_html|safe }}, [create a bot](/help/add-a-bot-or-integration) for
{{ integration_display_name }}. Make sure that you select
**Incoming webhook** as the **Bot type**:

![](/static/images/help/bot_types.png)

The API key for an incoming webhook bot cannot be used to read messages out
of Zulip. Thus, using an incoming webhook bot lowers the security risk of
exposing the bot's API key to a third-party service.

Construct the URL for the Beeminder bot using the bot's API key and your Zulip email.

The webhook URL should look like:

`{{api_url}}?api_key=BOT'S_API_KEY&email=foo@example.com`

Modify the parameters of the URL above where `api_key` is the API key of your Zulip bot
and `email` is your Zulip email.

* When creating or editing a goal in Beeminder, you can check the **Make private** option to make sure
the bot sends you private messages; otherwise, the bot will send messages to a public stream.

![](/static/images/integrations/beeminder/001.png)

* Copy the above URL and paste it in the `WEBHOOK` input option in the `reminders`
setting of your Beeminder account.

![](/static/images/integrations/beeminder/002.png)

{!congrats.md!}

![](/static/images/integrations/beeminder/003.png)
