Receive notifications in Zulip whenever a new version of an app
is pushed to Heroku using the Zulip Heroku plugin!

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

1. Go to your project on Heroku
   and click the **Resources** tab. Add the **Deploy Hooks** add-on.
   Select the **HTTP Post Hook** plan, and click **Provision**. Click on
   the **Deploy Hooks** add-on you just added.

1. Set **URL** to the URL constructed above. Click **Save and Send Test**
   to send a test message to your Zulip organization.

{!congrats.md!}

![](/static/images/integrations/heroku/001.png)
