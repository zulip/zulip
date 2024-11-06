# Zulip Lidarr integration

Receive Lidarr notifications in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to **Settings** in your Lidarr dashboard. Click **Connect**, and
   then click on the **+** icon.

1. Select **Webhook**, and set the webhook name to a name of your
   choice, such as `Zulip`. Select the scenarios you would like to
   receive notifications for. You may also enter tags if you would like
   to be notified about artists with specific tags.

1. Set **URL** to the URL generated above. Set **Method** to **POST**,
   and leave the **Username** and **Password** fields blank. Click
   **Save**, and you should receive a test message.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/lidarr/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
