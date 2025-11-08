# Zulip Dropbox integration

Get Dropbox notifications in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your [Dropbox apps page](https://www.dropbox.com/developers/apps),
   and select **Create app** near the top-right corner. Follow the on-screen
   instructions to create an app.

1. Once you've created the app, you will be redirected to the **Settings**
   tab for your app. Scroll down to the **Webhooks** section.

1. Go to the **Oauth 2** section, at the bottom of which you'll find a
   **Generate** button. Click on it to activate the app for your account.

    ![](/static/images/integrations/dropbox/oauth2_generate.png)

1. Set **Webhook URIs** to the URL generated above, and select **Add**.
   The status of the webhook should say **Enabled**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/dropbox/001.png)

### Related documentation

{!webhooks-url-specification.md!}
