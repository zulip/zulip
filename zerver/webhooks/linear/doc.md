# Zulip Linear integration

Get Linear notifications in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your team on Linear, and open **Settings**. Select **API**,
   and click on **New Webhook**.

1. Set **Webhook URL** to the URL generated above. Select the **Data
   change events** you'd like to receive notifications for, and click
   **Create Webhook**.

{end_tabs}

{!congrats.md!}

![Linear Integration](/static/images/integrations/linear/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

- [Linear webhook events documentation][linear-webhooks]

{!webhooks-url-specification.md!}

[linear-webhooks]: https://developers.linear.app/docs/graphql/webhooks
