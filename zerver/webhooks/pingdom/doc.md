# Zulip Pingdom integration

Zulip supports integration with Pingdom and can notify you of
uptime status changes from your Pingdom dashboard.

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. In Pingdom, open the **Integrations** menu, and click
   **Add integration**.

1. For **Type**, select **Webhook**. Set **Name** to a name of your
   choice, like `Zulip`, and set **URL** to the URL generated above.
   Make sure **Active** is toggle, and click **Save integration**.

1. Finally, when creating a new check or editing an existing check,
   toggle the integration created above in the **Connect Integrations**
   section for that check.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/pingdom/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
