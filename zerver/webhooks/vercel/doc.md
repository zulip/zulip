# Zulip Vercel integration

Get Zulip notifications for your Vercel deployments!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. In your Vercel dashboard, go to your project or team **Settings**, and select **Webhooks**.

1. Click **Create Webhook**. Set the **Endpoint URL** to the URL generated above.

1. Under **Events**, select the deployment events you wish to track (such as `deployment.created`, `deployment.succeeded`, `deployment.error`, `deployment.canceled`), and click **Create Webhook**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/vercel/001.png)

### Related documentation

- [Vercel Webhooks documentation](https://vercel.com/docs/webhooks/webhooks-api)

{!webhooks-url-specification.md!}
