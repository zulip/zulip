Get Zulip notifications for your Librato/AppOptics alerts or snapshots!

### Set up notifications for Alerts

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}
   The default stream name is **librato** and default topic name is
   **Alert alert_name**.

1. Go to your AppOptics/Librato homepage, and click on **Settings**
   on the left. Select **Notification Services**, and click on
   **Webhooks**.

1. Set **Title** to a title of your choice, such as `Zulip`. Set **URL**
   to the URL constructed above, and click **Add**. When you create a
   new **Alert**, you can enable this webhook under the **Notification
   Services** tab.

{!congrats.md!}

![](/static/images/integrations/librato/001.png)

### Set up notifications for Snapshots

Because of limitations in Librato's API, you need to use the
[Slack integration](./slack) to get Librato snapshots sent into Zulip.

The default stream name is **librato** and default topic name is
**snapshots**.

To send a snapshot, just click on one of your charts, use
the **send a snapshot** option and add the proper integration.

![](/static/images/integrations/librato/008.png)

{!congrats.md!}

![](/static/images/integrations/librato/009.png)
