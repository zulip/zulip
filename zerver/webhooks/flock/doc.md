# Zulip Flock integration

Get Zulip notifications from your Flock channels.

{start_tabs}

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. In Flock, click on **Apps** in the bottom-right corner.

1. Select **Admin Panel**, and then select **Webhooks**.

1. Next to **Outgoing Webhook**, select **Add**.

1. Set **Send messages from a channel** to the Flock channel you'd like
   to be notified about.

1. Set **Name that the webhook will post as** to a name of your choice,
   such as `Zulip`.

1. Set **Callback URL** to the URL generated above, and select **Save Settings**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/flock/001.png)

### Related documentation

{!webhooks-url-specification.md!}
