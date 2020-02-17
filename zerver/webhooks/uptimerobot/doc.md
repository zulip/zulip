Receive Zulip notifications from Uptime Robot!

1. {!create-stream.md!}

1.     {!create-a-bot-indented.md!}

    Construct the URL for the {{ integration_display_name }}
    bot using the bot's API key and the desired stream name:

    `{{ api_url }}{{ integration_url }}?api_key=abcdefgh&stream=stream%20name&`

    Modify the parameters of the URL above, where `api_key` is the API key
    of your Zulip bot, and `stream` is the URL-encoded stream name you want the
    notifications sent to. If you do not specify a `stream`, the bot will
    send notifications via PMs to the creator of the bot.

1. Go to **My Settings** on Uptime Robot, and select **Add Alert Contact**.
   Set **Alert Contact Type** as webhook.

1. Set **Friendly Name** to a name of your choice, such as `Zulip`. Set **URL to notify** to the
   URL constructed above. Select **Send as JSON (application/json)** under **POST Value(JSON Format)**.

1. Set **POST Value(JSON Format)** to


   >{
   >    "monitorID":"*monitorID*",
   >    "monitorURL":"*monitorURL*",
   >    "monitorFriendlyName":"*monitorFriendlyName*",
   >    "alertType":"*alertType*",
   >    "alertTypeFriendlyName":"*alertTypeFriendlyName*",
   >    "alertDetails":"*alertDetails*",
   >    "alertFriendlyDuration":"*alertFriendlyDuration*"
   >}


1. Choose **Enable Notifications For** to whatever you prefer.
   Save the form.

{!congrats.md!}

![](/static/images/integrations/uptimerobot/001.png)
