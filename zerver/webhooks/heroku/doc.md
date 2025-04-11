# Zulip Heroku integration

Receive notifications in Zulip whenever a new version of an app
is pushed to Heroku using the Zulip Heroku plugin!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to the Dashboard page for your app and to the dropdown menu below “More”.

1. Click on View Webhooks.

1. Click on Create Webhook and set the Payload URL to the URL generated above.

1. Select Event Types that you want to receive alerts for and click Add Webhook.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/heroku/001.png)

### Related documentation

{!webhooks-url-specification.md!}
