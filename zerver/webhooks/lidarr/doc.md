Receive Lidarr notifications in Zulip!

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

1. Go to your Lidarr dashboard. Click **Settings** and
    click **Connect**. Click the **+** icon.

1. Select **Webhook** and set the name of the webhook to any name
    of your choice (e.g **Zulip**). Select the scenarios you would like
    to receive notifications for. You may also enter tags if you would like
    to be notified about artists with specific tags.

1. Set **URL** to the **URL** constructed above. Set **Method** to **POST**
    and leave the **Username** and **Password** fields blank.

1. Click **Save** and you should receive a test message.

{!congrats.md!}

![](/static/images/integrations/lidarr/001.png)
