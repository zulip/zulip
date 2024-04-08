Get Zulip notifications for your Netlify deployments!

{start_tabs}

1. {!create-stream.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your Netlify project, and click **Settings**. Click **Build & deploy**, and select **Deploy notifications**.
   Click **Add Notification**, and select **Outgoing webhook**.

1. Select an **Event**, and set **URL to notify** to the URL constructed above. Click **Save**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/netlify/001.png)

!!! tip ""

    For more information regarding Netlify webhooks, see: [Netlify's webhook documentation][1].

[1]: https://www.netlify.com/docs/webhooks/

### Related documentation

{!webhooks-url-specification.md!}
