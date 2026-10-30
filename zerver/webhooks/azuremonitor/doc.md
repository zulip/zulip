# Zulip Azure Monitor integration

Get Zulip notifications for your
[Azure Monitor](https://learn.microsoft.com/en-us/azure/azure-monitor/overview)
alerts!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your [Azure portal](https://portal.azure.com). Navigate to
   **Monitor**, then **Alerts**, then
   [**Action groups**](https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/action-groups).
   Select **Create**.

1. Enter an **Action group name** and **Display name**.

1. Go to the **Actions** tab. Set **Action type** to
   [**Webhook**](https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/action-groups#webhook),
   enter a **Name**, and set **URI** to the URL generated above.
   Make sure **Enable the
   [common alert schema](https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/alerts-common-schema)**
   is set to **Yes**, and select **OK**.

1. Select **Review + create**, then **Create**.

1. Assign this action group to any
   [alert rule](https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/alerts-create-metric-alert-rule)
   you want Zulip notifications for.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/azuremonitor/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
