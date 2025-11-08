# Zulip Heroku integration

Receive notifications in Zulip whenever a new version of an app
is pushed to Heroku using the Zulip Heroku plugin!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. In your project on Heroku, go to the **Resources** tab.

1. Add the **Deploy Hooks** add-on. Select the **HTTP Post Hook** plan,
   and click **Provision**. Click on the **Deploy Hooks** add-on you
   just added.

1. Set **URL** to the URL generated above. Click **Save and Send Test**
   to send a test message to your Zulip organization.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/heroku/001.png)

### Related documentation

{!webhooks-url-specification.md!}
