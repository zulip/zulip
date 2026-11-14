# Zulip Vercel integration

Get Zulip notifications for your Vercel deployments!

!!! warn ""

    **Note**: Vercel only supports account webhooks on its Pro and
    Enterprise plans.

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. In Vercel, select your team, and go to **Settings**. Select
   **Webhooks**.

1. Under **Events**, select the **Deployment** events you'd like to be
   notified about. This integration supports **Deployment Created**,
   **Deployment Succeeded**, **Deployment Error**, **Deployment
   Cancelled**, and **Deployment Promoted**.

1. Choose the projects you'd like to receive notifications for.

1. Set **Endpoint URL** to the URL generated above, and click **Create
   Webhook**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/vercel/001.png)

### Related documentation

- [Vercel's webhooks documentation](https://vercel.com/docs/webhooks)

{!webhooks-url-specification.md!}
