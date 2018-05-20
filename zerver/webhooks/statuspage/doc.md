Get Zulip notifications for your Statuspage.io subscriptions!

### Enabling webhook notifications for your organization

1. Go to your Statuspage Dashboard, and click on **Notifications**
   on the bottom-left corner. Select the **Webhook** tab. If webhook
   notifications are disabled, simply click on the **reactivate webhook
   notifications now** link to enable them.

1. Under **Notification Delivery Types**, select **Webhook**. Set up
   your **Subscription Types** as appropriate, and click on **Save Changes**.

### Subscribing to webhook notifications

Now that you have enabled webhook notifications for your organization, users
can subscribe to these notifications by performing the following steps:

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

1. Go to the organization's Statuspage site (for instance,
   `example.statuspage.io`). Click on **Subscribe To Updates**.

1. Set the URL to the URL constructed above, and provide an email address.
   Statuspage will send notifications to this email if your webhook URL
   fails. Click on **Subscribe To Notifications**.

{!congrats.md!}

![](/static/images/integrations/statuspage/001.png)
