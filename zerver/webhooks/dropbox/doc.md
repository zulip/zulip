Get Dropbox notifications in Zulip!

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

1. Go to your [Dropbox apps page](https://www.dropbox.com/developers/apps).
   Click on **Create app** near the top-right corner, and follow the on-screen
   instructions to create an app. Once you've created the app, you will be
   redirected to the **Settings** tab for your app. Scroll down to the
   **Webhooks** section.

1. Go to the **Oauth 2** section, at the bottom of which you'll find a **Generate**
   button. Click on it to activate the app for your account.

    ![](/static/images/integrations/dropbox/oauth2_generate.png)

1. Set **Webhook URIs** to the URL constructed above and click **Add**.
   The status of the webhook should say **Enabled**.

{!congrats.md!}

![](/static/images/integrations/dropbox/001.png)
