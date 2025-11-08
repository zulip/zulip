# Zulip Grafana integration

See your Grafana dashboard alerts in Zulip!

### Create Zulip bot for Grafana alerts

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

{end_tabs}

### Instructions for Grafana 8.3 and above

{start_tabs}

1. In Grafana, go to **Alerting**. Click on **Contact points**, and then
   **Add contact point**.

1. Set a name for the contact point, such as `Zulip`. Under
   **Integration**, choose  **Webhook**, and set **URL** to the URL
   generated above. Under **Optional Webhook settings**, choose **POST**
   as the **HTTP method**. Click on **Test** to send a test
   notification, and if it's successful, click **Save contact point**.

1. Go to **Notification policies**, and create a new policy, e.g., a
   **New nested policy** of the **Default policy**. Set the **Matching
   label** as **Zulip** = 1, and set the **Contact point** to the one
   created above. Click **Save policy**.

1. Go to **Alert rules**, and click **Create alert rule**. Make sure you
   set a **Rule name**. In the **Notifications** section, add a label
   that matches the label created for the notification policy above.
   You can customize the **query and alert condition**, **alert
   evaluation behavior**, and other conditions for your alerts. When
   you're done, click **Save rule**.

{end_tabs}

### Instructions for Grafana 8.2 and below

{start_tabs}

1. In Grafana, go to **Alerting**. Click on **Notification channels**.

1. Configure **Edit Notification Channel** as appropriate for your
   alert notification. Set a name for the notification channel, such
   as `Zulip`. Under **Type**, choose **webhook**. In **Webhook
   Settings**, set **URL** to the URL generated above. Under **HTTP
   method**, choose **POST**. Click **Save**.

1. Create an alert. In your new alert rule, go to the **Notifications**
   section. Click on the button next to **Send to** and select the
   webhook notification channel you created above. You can also choose
   to write a message, which will be included in your Zulip
   notifications.

1. Return to **Notification channels**, and click **Send Test**. You
   should see a Grafana test alert notification in Zulip.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/grafana/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
