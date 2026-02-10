# Zulip Statuspage integration

Get Zulip notifications for your Statuspage.io subscriptions!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your Statuspage Dashboard, and click on **Notifications**
   near the bottom-left corner. Select the **Webhook** tab. If webhook
   notifications are disabled, click **reactivate webhook
   notifications now** to enable them. Click on the
   **gear** (<i class="fa fa-cog"></i>) icon next to
   **Subscribers**, and select **Add subscriber**.

1. Set **Subscriber type** to **Webhook**. Set **Endpoint URL** to
   the URL generated above, and provide an email address. Statuspage
   will send email notifications to this address if the webhook endpoint
   fails. Click **Add Subscriber**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/statuspage/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
