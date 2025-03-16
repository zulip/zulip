# Zulip OpenSearch integration

Get OpenSearch alerts in Zulip!

### Create Zulip bot for OpenSearch notifications

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

{end_tabs}

### Create an OpenSearch notification channel

{start_tabs}

1. From the OpenSearch Menu, select **Notifications** from the
   **Management** section, and click **Create channel**.

1. Fill in the name and description. For **Channel type**, select
   **Custom webhook**. Set the **Method** to **POST**, and the **Define
   endpoints by** to **Webhook URL**. Paste the URL generated above into the
   **Webhook URL** field.

1. Click **Send test message**. A test message should appear in Zulip. Click
   **Create** to save the notification channel.

{end_tabs}

### Create an OpenSearch alert monitor

{start_tabs}

1. To use the notification channel created above in an alerting action,
   create an alert monitor. From the OpenSearch menu, select
   **Alerting** from the **OpenSearch Plugins** section, and click
   **Create monitor**.

1. [Configure the alert monitor][alert-monitor] by entering the
   monitor details, selecting the index to monitor, and adding a
   [trigger][trigger]. In the **Actions** section, select the notification
   channel created above as the **Notification** action.

1. OpenSearch sends notifications as plain text, so you will want to use a
   **Message template** to format your messages in Zulip. To generate the
   topic of your Zulip messages via the notification content, you can use
   the first line of your template to do so. It must be formatted as
   **topic: DYNAMIC_TOPIC_CONTENT**, and all message content should start on
   the second line of the template. For example, this template was used to
   generate the example screenshot below:

    ```
    {% raw %}
    topic: {{ctx.monitor.name}}
    Alert of severity **{{ctx.trigger.severity}}** triggered by **{{ctx.trigger.name}}** at {{ctx.periodStart}} UTC.
    {% endraw %}
    ```

    !!! tip ""

        The **Message template** supports Markdown and Mustache template
        variables.

1. Click **Send test message** to test the integration, and click **Create**
   to save the monitor.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/opensearch/001.png)

### Related documentation

{!webhooks-url-specification.md!}

* [OpenSearch alert monitor][alert-monitor]

[alert-monitor]: https://opensearch.org/docs/latest/observing-your-data/alerting/index/#creating-an-alert-monitor
[trigger]: https://opensearch.org/docs/latest/observing-your-data/alerting/triggers/
