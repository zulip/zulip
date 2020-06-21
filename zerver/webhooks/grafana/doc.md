See your Grafana dashboard alerts in Zulip!

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

1. In Grafana, go to **Alerting**. Click on **Notification channels**.
   Configure **Edit Notification Channel** as appropriate for your
   alert notification. Set the name. Under **Type**, choose **webhook**.
   In **Webhook Settings**, set **URL** to the URL constructed above.
   Under **HTTP method**, choose **POST**. Click Save.

1. Create an alert. Within your new alert rule, scroll down
   to the **Notifications** section. Click on the button next to **Send to**
   and select the webhook notification channel you just made. You can also
   choose to write a message, which will be included in the Zulip notifications.

1. Return to **Notification channels**. You may now click **Send Test** and
   you will see a Grafana test alert notification in Zulip.

{!congrats.md!}

![](/static/images/integrations/grafana/001.png)
