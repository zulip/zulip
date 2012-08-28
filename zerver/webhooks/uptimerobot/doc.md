# Zulip UptimeRobot integration

Receive Zulip notifications from UptimeRobot!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. On UptimeRobot, go to **My Settings**, and select **Add Alert Contact**.

1. Set **Alert Contact Type** to **webhook**, set **Friendly Name** to
   a name of your choice, such as `Zulip`, and set **URL to notify** to the
   URL generated above.

1. Under **POST Value (JSON Format)**, select **Send as JSON (application/json)**,
   and then set the value to:

         {
            "monitor_url":"*monitorURL*",
            "monitor_friendly_name":"*monitorFriendlyName*",
            "alert_type":"*alertType*",
            "alert_type_friendly_name":"*alertTypeFriendlyName*",
            "alert_details":"*alertDetails*",
            "alert_friendly_duration":"*alertFriendlyDuration*"
         }

1. Set **Enable Notifications For** the [events](#filtering-incoming-events)
   you'd like to be notified about, and save the form.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/uptimerobot/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
