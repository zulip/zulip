# Clients in Zulip

`zerver.models.Client` is Zulip's analogue of UserAgent.

## Analytics
A `Client` is used to sort messages into client categories such as
`ZulipElectron` on the `/stats`
[page](https://chat.zulip.org/stats). For more information see,
[Analytics](analytics.html).

## Webhook Integrations
Auth decorators for incoming webhooks defined in `zerver/decorators.py`
(such as `api_key_only_webhook_view`) set the `request.client`
attribute on `request` (Django
[HttpRequest](https://docs.djangoproject.com/en/1.8/ref/request-response/#django.http.HttpRequest))
objects. `request.client` is then passed to `check_send_message`.
`check_send_message` accepts a `Client` as a positional argument and is
used to validate and send a public (stream) message. For more information,
see [the webhook walkthrough](webhook-walkthrough.html).
