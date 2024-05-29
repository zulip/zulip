See your Splunk Search alerts in Zulip!

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

    If you do not specify a topic, the name of the search is used
    (truncated to fit if needed).

1. In the Splunk search app, execute the search you'd like to be
   notified about. Click on **Save As** in the top-right corner,
   and select **Alert**.

1. Configure the **Settings** and **Trigger Conditions** for your search
   as appropriate. Under **Trigger Actions**, click **Add Actions**,
   and select **Webhook**. Set **URL** to the URL constructed above,
   and click **Save**.

!!! tip ""

    You can create as many search alerts as you like, with whatever
    channel and topic you choose. Just update your webhook URL as
    appropriate for each one, and make sure the channel exists.

{!congrats.md!}

![](/static/images/integrations/splunk/001.png)
