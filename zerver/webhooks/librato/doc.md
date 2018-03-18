Get Zulip notifications for your Librato alerts or snapshots!

{!create-stream.md!}

{!create-bot-construct-url.md!}

The default stream name is **librato** and default topic name is
**Alert alert_name**.

### Alerts configuration

Login into your Librato account and switch to the Integrations
page:

![](/static/images/integrations/librato/001.png)

From there, select **Webhook** integration:

![](/static/images/integrations/librato/002.png)

Fill in the title and for the URL, fill in the URL we created
above:

![](/static/images/integrations/librato/003.png)

Next, go to your Alerts page:

![](/static/images/integrations/librato/004.png)

Choose the alert conditions and enable the your new webhook
under **Notification Services**:

![](/static/images/integrations/librato/005.png)

{!congrats.md!}

![](/static/images/integrations/librato/006.png)

### Snapshot configuration

Because of limitations in Librato's API, you need to use the
Slack integration to get Librato snapshots sent into Zulip.

![](/static/images/integrations/librato/007.png)

Default stream name is **librato** and default topic name is
**snapshots**.

To send a snapshot, just click on one of your charts, use
the **send a snapshot** option and add the proper integration.

![](/static/images/integrations/librato/008.png)

{!congrats.md!}

![](/static/images/integrations/librato/009.png)
