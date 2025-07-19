# Zulip Redmine integration

Get Zulip notifications for your Redmine projects!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Install the [Redmine webhook plugin](https://github.com/suer/redmine_webhook) on your Redmine instance.

1. In your Redmine project settings, go to the **Webhooks** tab and click **New webhook**.

1. Set **URL** to the URL generated above. Select the events you'd like to be notified about.

1. Click **Save** to enable the webhook.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/redmine/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
