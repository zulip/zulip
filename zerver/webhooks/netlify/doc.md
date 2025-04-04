# Zulip Netlify integration

Get Zulip notifications for your Netlify deployments!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your Netlify project, and click **Settings**. Click **Build & deploy**,
   and select **Deploy notifications**.
   Click **Add Notification**, and select **HTTP POST request**.

1. Select an **Event**, and set **URL to notify** to the URL generated above.
   Click **Save**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/netlify/001.png)

### Related documentation

- [Netlify HTTP Post Request documentation](https://docs.netlify.com/site-deploys/notifications/#http-post-request)

{!webhooks-url-specification.md!}
