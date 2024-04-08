Get Zulip notifications for your Semaphore builds!

{start_tabs}

1. {!create-stream.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. In Semaphore 2.0, under **Configuration** select **Notifications**. Click on
   **Create New Notification**. Add the the URL constructed above to the Webhook
   **Endpoint** field.

    If you are using Semaphore Classic, in your Semaphore project, go to
   **Project settings**, and select the **Notifications** tab. Click on
   **Webhooks**, and click **+ Add Webhook**.

1. Set **URL** to the URL constructed above, and click
   **Save Settings**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/semaphore/001.png)

### Related documentation

{!webhooks-url-specification.md!}
