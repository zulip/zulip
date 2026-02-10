# Zulip Splunk integration

See your Splunk Search alerts in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

    !!! tip ""

        If you do not specify a topic, the name of the search will be used
        as the topic (truncated if it's too long).

1. In the Splunk search app, execute the search you'd like to be
   notified about. Click on **Save As** in the top-right corner,
   and select **Alert**.

1. Configure the **Settings** and **Trigger Conditions** for your search
   as appropriate. Under **Trigger Actions**, click **Add Actions**,
   and select **Webhook**. Set **URL** to the URL generated above,
   and click **Save**.

!!! tip ""

    You can create as many search alerts as you like, with whatever
    channel and topic you choose. Just generate the webhook URL as
    appropriate for each one.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/splunk/001.png)

### Related documentation

{!webhooks-url-specification.md!}
