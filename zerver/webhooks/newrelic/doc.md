New Relic can send messages to a Zulip stream for incidents.

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

1. On [New Relic](https://one.newrelic.com),
  select **Alerts & AI**.

1. Navigate to **Notification channels**.

1. Create a new notification channel. Select channel type of **Webhook**, choose a name (e.g. "Zulip"), enter the webhook url created earlier as **Base Url**.

1. It should look like:
  ![](/static/images/integrations/newrelic/newrelic.png)

1. The webhook works with the default payload, click **Create channel**.

1. After creating the channel send a test notification to make sure it works.

{!congrats.md!}

![](/static/images/integrations/newrelic/opened.png)
![](/static/images/integrations/newrelic/ack.png)
![](/static/images/integrations/newrelic/closed.png)
