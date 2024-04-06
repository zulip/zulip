Receive Zulip notifications from UptimeRobot!

{start_tabs}

1. {!create-stream.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

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

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/uptimerobot/001.png)

### Related documentation

{!webhooks-url-specification.md!}
