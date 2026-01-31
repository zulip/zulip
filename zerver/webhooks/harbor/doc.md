# Zulip Harbor integration

Get Zulip notifications for your [Harbor](https://goharbor.io/) projects!

Harbor's webhooks feature is available in version 1.9 and later.

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your Harbor **Projects** page and open a project.

1. Click on the **Webhooks** tab and then click on the **New Webhook** button.

1. Enter a name for your webhook (e.g., "Zulip Notifications").

1. Select `http` as the **Notify Type**.

1. Select `Default` as the **Payload Format**.

1. Check the boxes for the events you want to receive notifications for.

1. Select **Verify Remote Certificate** if your Zulip server uses HTTPS.

1. Set **Endpoint URL** to the URL generated above, and click on **Add**.

![](/static/images/integrations/harbor/002.png)

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/harbor/001.png)

{% if all_event_types is defined %}

{!event-filtering-additional-feature.md!}

{% endif %}

### Related documentation

{!webhooks-url-specification.md!}
