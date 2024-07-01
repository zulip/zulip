# Zulip Freshping integration

Receive Freshping notifications in Zulip!

{start_tabs}

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your **Freshping** dashboard, and select **Settings**.

1. Select **Integrations**, and then select **Create Integration**
   under **Webhooks**.

1. Set **Domain URL** to the URL generated above, and select **Create**.

1. You can test the webhook by clicking **Test** to ensure it is
   configured correctly.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/freshping/001.png)

{% if all_event_types is defined %}

{!event-filtering-additional-feature.md!}

{% endif %}

### Related documentation

{!webhooks-url-specification.md!}
