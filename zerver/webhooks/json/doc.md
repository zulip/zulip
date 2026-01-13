# Zulip JSON formatter

Render JSON payloads nicely in a Zulip code block! This is
particularly useful when you want to capture a webhook payload as part
of [writing an incoming webhook integration][incoming-webhooks-overview].

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Configure your application to send the webhook
   payload to the **URL** generated above.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/json/001.png)

### Related documentation

{!webhooks-url-specification.md!}

[incoming-webhooks-overview]: https://zulip.readthedocs.io/en/latest/webhooks/incoming-webhooks-overview.html
