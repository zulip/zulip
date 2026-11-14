# Zulip Famulor integration

Receive Famulor call, conversation, and booking notifications in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. In [Famulor](https://app.famulor.io), open the assistant and go to
   **Settings > Automations > Call completed**. Choose **Webhook**,
   paste the URL generated above, and save. Use **Send test** to
   confirm delivery.

1. To also receive `conversation.ended`, `booking.created`,
   `booking.cancelled`, and `booking.rescheduled`, register that same
   URL as a [signed webhook subscription][webhook-subscriptions], or
   paste it into a booking event type's **Webhook URL**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/famulor/001.png)

{!event-filtering-additional-feature.md!}

### Signature

The assistant **Call completed** webhook is unsigned. Workspace
subscriptions, booking event types, and the inbound variable webhook
send `X-Famulor-Signature: sha256=<hex HMAC of the raw body>`. Zulip
authenticates this integration with the bot API key in the webhook
URL, as it does for other incoming webhooks, and does not verify that
signature. Keep the generated URL private.

Famulor 1.0 post-call and conversation-ended webhooks
(`app.famulor.de`) can use this same URL.

### Related documentation

* [Post-call webhooks][post-call]
* [Signed webhook subscriptions][webhook-subscriptions]
* [Built-in calendar webhooks][native-calendar]
* [Legacy post-call webhook (Famulor 1.0)][legacy-post-call]
* [Legacy conversation-ended webhook (Famulor 1.0)][legacy-conversation]

{!webhooks-url-specification.md!}

[post-call]: https://docs.famulor.io/assistants/webhooks
[webhook-subscriptions]: https://docs.famulor.io/automations/webhook-subscriptions
[native-calendar]: https://docs.famulor.io/assistants/native-calendar
[legacy-post-call]: https://docs.famulor.io/api-v1/webhooks/post-call
[legacy-conversation]: https://docs.famulor.io/api-v1/webhooks/conversation-ended
