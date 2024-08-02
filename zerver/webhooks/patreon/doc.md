# Zulip Patreon integration

Get Patreon notifications in Zulip!

{start_tabs}

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Login to your Patreon developer account, navigate to your Patreon Portal, and
    click on [My Webhooks][1].

1. Paste the URL generated above in the webhook URL field, and click the
    **plus** (**+**) button. Enable the [events](#filtering-incoming-events) you
    would like to receive notifications for, and click **Send Test**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/patreon/001.png)

{!event-filtering-additional-feature.md!}

[1]: https://www.patreon.com/portal/registration/register-webhooks

### Related documentation

- [Patreon trigger documentation](https://docs.patreon.com/#triggers-v2)

- [Patreon webhook documentation](https://docs.patreon.com/#webhooks)

{!webhooks-url-specification.md!}
