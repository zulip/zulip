# Zulip Flock integration

Get Zulip notifications from your Flock channels.

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. In Flock, click on **Apps** in the bottom-right corner. Got to the
   **Admin Panel**, and click on **Webhooks**. Select **Outgoing
   Webhook**, and click **Add**.

1. Set **Send messages from a channel** to the Flock channel you'd like
   to be notified about. Set **Name that the webhook will post as** to a
   name of your choice, such as `Zulip`. Finally, set **Callback URL**
   to the URL generated above, and click **Save Settings**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/flock/001.png)

### Related documentation

{!webhooks-url-specification.md!}
