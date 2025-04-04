# Zulip Semaphore integration

Get Zulip notifications for your Semaphore builds!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. In the **Configuration** section of the sidebar in Semaphore, select
   **Notifications**. Click on **Create New Notification**.

1. Add a name for the notification, such as `Zulip`, and configure any
   rules you'd like for the notifications. Add the URL generated above
   to the Webhook **Endpoint** field, and click **Save Changes**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/semaphore/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
