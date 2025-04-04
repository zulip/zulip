# Zulip Radarr integration

Receive Radarr notifications in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your Radarr dashboard. Open **Settings**, and select **Connect**.
    Click the plus (**+**) icon.

1. Select **Webhook**, and set the name of the webhook to any name of your
    choice, such as `Zulip`. Select the scenarios you would like to receive
    notifications for. You may also enter tags if you would like to be
    notified about movies with specific tags.

1. Set **URL** to the URL generated above, and set **Method** to
    **POST**. Leave the **Username** and **Password** fields blank. Click **Save**, which will send a test message to Zulip.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/radarr/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
