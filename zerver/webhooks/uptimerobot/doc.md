Receive Zulip notifications from UptimeRobot!

1. {!create-stream.md!}

1. {!create-a-bot-indented.md!}

    Construct the URL for the {{ integration_display_name }}
    bot using the bot's API key and the desired stream name:

    `{{ api_url }}{{ integration_url }}?api_key=abcdefgh&stream=stream%20name&`

    Modify the parameters of the URL above, where `api_key` is the API key
    of your Zulip bot, and `stream` is the URL-encoded stream name you want the
    notifications sent to. If you do not specify a `stream`, the bot will
    send notifications via PMs to the creator of the bot.

1. On UptimeRobot, go to **My Settings** and select **Add Alert Contact**.
   Set **Alert Contact Type** to **webhook**.

1. Set **Friendly Name** to a name of your choice, such as `Zulip`. Set **URL to notify** to the
   URL constructed above. Under **POST Value (JSON Format)**, select **Send as JSON (application/json)**.

1. Set **POST Value(JSON Format)** to:

      ```
      {
         "monitor_url":"*monitorURL*",
         "monitor_friendly_name":"*monitorFriendlyName*",
         "alert_type":"*alertType*",
         "alert_type_friendly_name":"*alertTypeFriendlyName*",
         "alert_details":"*alertDetails*",
         "alert_friendly_duration":"*alertFriendlyDuration*"
      }
      ```

1. Set **Enable Notifications For** to whichever events you want to notify on.
   Save the form.

{!congrats.md!}

![](/static/images/integrations/uptimerobot/001.png)
