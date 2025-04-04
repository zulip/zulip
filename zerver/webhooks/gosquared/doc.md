# Zulip GoSquared integration

Receive GoSquared notifications in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your project's **Settings**, and click on **Services**.
   Scroll down and next to **Webhook**, click on **Connect**. Click
   **Add new**.

1. Set **Webhook URL** to the URL generated above. Set **Name** to a
   name of your choice, such as `Zulip`. Click **Save Integration**.

1. In your project's **Settings**, click on **Notifications**. Click
   **Add new notification**.

1. Under **Trigger**, you can configure when notifications are
   triggered. Under **Delivery**, toggle the **Webhook** checkbox,
   and click **Add**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/gosquared/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
