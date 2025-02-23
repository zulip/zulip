# Zulip OpenSearch integration

Get notifications from OpenSearch in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Append `&topic=topic+name`
   to the URL generated above, where `topic+name` is the
   URL-encoded name of the topic you want to use.

1. In OpenSearch, click the **gear** (<i class="fa fa-cog"></i>) icon in the
   bottom-left corner. Click on **Settings and setup**. In the sidebar,
   click on **Channels** under **Notification channels**. Click **Create
   channel**.

1. Fill in the name and description. For **Channel type**, select
   **Custom webhook**. The **Method** should be **POST**, and the **Define
   endpoints by** option should be **Webhook URL**. Paste the URL generated
   and updated above into the **Webhook URL** field.
   Set the `Content-Type` header to `application/json`.

1. Click **Send test message**. A test message should
   appear in Zulip. Save the channel by selecting **Create**.

1. This integration supports both plain text and JSON payloads.
   OpenSearch sends notifications as plain text by default. To send JSON payloads,
   format notification templates as a JSON object. The JSON object must contain a
   `message` key with the message content. You can also include a `topic`
   key to specify the topic the message should be sent to.
   For example, here is a template for an alerting trigger:

    ```json
    {% raw %}
    {
      "topic": "{{ctx.monitor.name}}",
      "message": "Entered alert status.\n- Trigger: {{ctx.trigger.name}}\n- Severity: {{ctx.trigger.severity}}\n- Period start: {{ctx.periodStart}} UTC"
    }
    {% endraw %}
    ```

1. To use the integration in an alerting action, go to your OpenSearch analytics
   workspace and click on **Alerts** under **Alerting** in the sidebar.
   Click on **Create monitor**. Fill in the monitor name,
   and configure the monitor as needed. In the **Triggers** section,
   click on **Add trigger**. Fill in the trigger name, and configure the
   trigger conditions as needed. In the **Actions** section, there should
   be a **Notification** action already added. Fill in the action name,
   and select the notification channel you created earlier. Update the
   message template as needed. Click **Send test message** to test the integration. Click **Create** to save the monitor.

   See [OpenSearch alerting documentation](https://opensearch.org/docs/latest/observing-your-data/alerting/) for more information on setting up alerts,
   and [OpenSearch alerting action variables](https://opensearch.org/docs/latest/observing-your-data/alerting/actions/#actions-variables) for more information on available variables.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/opensearch/001.png)

### Related documentation

{!webhooks-url-specification.md!}
