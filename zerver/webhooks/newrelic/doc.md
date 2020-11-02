New Relic can send messages to a Zulip stream for alerts and
deploys.

{!create-stream.md!}

{!create-bot-construct-url.md!}

Next, on [New Relic](https://one.newrelic.com), in the navigation bar
at the topc, click **Alerts & AI**, then **Notification channels**.
In the top right on that page, click **New notification channel**.
Under **Channel details**, select channel type **Webhook**, choose
a name (e.g. "Zulip"), enter the webhook URL created earlier as
**Base Url** and leave everything else as is:

![](/static/images/integrations/newrelic/001.png)

After saving the web hook, trigger a test notification to make sure
everything works correctly.

{!congrats.md!}

![](/static/images/integrations/newrelic/002.png)
