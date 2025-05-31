# Zulip Vercel integration

Get Zulip notifications for your Vercel projects!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Use the [Integration Console](https://vercel.com/dashboard/integrations/console) on Vercel to create an integration. When setting it up, ensure that the webhook URL points to the integration URL you generated in the previous step.

1. For the Redirect URL, specify a server that facilitates connecting user accounts to the integration. If you're testing or need a quick solution, you can use a temporary server—like this simple [example server](https://gist.github.com/apoorvapendse/a5f0a569504e4d802566ffbac10613b1)—to manage the connection process efficiently.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/vercel/001.png)

### Related documentation

- [Configuring Vercel webhooks](https://vercel.com/docs/observability/webhooks-overview#configure-a-webhook)

{!webhooks-url-specification.md!}
