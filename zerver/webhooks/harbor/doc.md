# Zulip Harbor integration

Get Zulip notifications for your [Harbor](https://goharbor.io/) projects!

Harbor's webhooks feature is available in version 1.9 and later.

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your Harbor **Projects** page, open a project, and click on the **Webhooks** tab.

1. Set **Endpoint URL** to the URL generated above, and click on **Continue**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/harbor/001.png)

{% if all_event_types is defined %}

{!event-filtering-additional-feature.md!}

{% endif %}

### Related documentation

{!webhooks-url-specification.md!}
