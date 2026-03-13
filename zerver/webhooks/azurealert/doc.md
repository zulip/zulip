# Zulip Azure Alerts integration

Get Zulip notifications for your Azure Monitor alerts!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your [Azure portal](https://portal.azure.com). Navigate to
   **Monitor**, then **Alerts**.

1. Click on **Action groups**, and then **Create** to create a new
   action group.

1. Under the **Actions** tab, set **Action type** to **Webhook**.
   Set **URI** to the URL generated above.

1. Make sure **Enable the common alert schema** is set to **Yes**,
   and click **OK** to save.

1. Assign this action group to any alert rule you want Zulip
   notifications for.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/azurealert/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
