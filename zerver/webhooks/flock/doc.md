Get Zulip notifications from your Flock channels.

{start_tabs}

1. {!create-stream.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Click on **Apps** in the bottom-right corner.
   Click on **Admin Panel**, and click on **Webhooks**.
   Next to **Outgoing Webhook**, click on **Add**.

1. Set **Send messages from a channel** to the channel you'd like to be notified about.
   Set **Name that the webhook will post as** to a name of your choice, such as `Zulip`.
   Set **Callback URL** to the URL created above, and click **Save Settings**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/flock/001.png)

### Related documentation

{!webhooks-url-specification.md!}