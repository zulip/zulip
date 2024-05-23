See your Grafana dashboard alerts in Zulip!

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

### Instructions for Grafana 8.3 and above

1. In Grafana, go to **Alerting**. Click on **Contact points**, and
   then **Add contact point**.  Configure the new contact point as
   follows: set the name; under **Integration** choose Webhook, and
   set **URL** to the URL constructed above; under **Optional Webhook
   settings** choose **POST** as the **HTTP method**.  Click on
   **Test** to send a test notification and if all is good, click on
   **Save contact point**.
1. Under **Notification policies** create a new policy (for example, a
   **New nested policy** of the **Default policy**), setting the
   **Matching label** as **Zulip** = 1, and selecting the **Contact
   point** as the one created in the step above. Click on **Save
   policy**.
1. Under **Alert rules**, click on **Create alert rule**, where you
   will specify the conditions to fire the alert. Make sure you set
   the **Rule name**, and in the **Notifications** section add a label
   that matches the label created in the step above. Customize the
   **query and alert condition**, **alert evaluation behavior**, etc.
   and click on **Save rule**.

### Instructions for Grafana 8.2 and below

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
