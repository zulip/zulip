# Zulip Heroku integration

Receive notifications in Zulip whenever a new version of an app
is pushed to Heroku using the Zulip Heroku plugin!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. From the Heroku dashboard page for your app, click the “More” menu at the top-right, and select **View Webhooks**.

1. Click **Create Webhook**, and set the **Payload URL** to the URL generated above. From **Event Types**, select the events that you want to receive notifications for, and click **Add Webhook**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/heroku/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}

- [Heroku App webhooks documentation][Heroku Webhooks Documentation]

[Heroku Webhooks Documentation]: https://devcenter.heroku.com/articles/app-webhooks
