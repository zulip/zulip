# Zulip GitHub integration

Get GitHub notifications in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. Decide where to send {{ integration_display_name }} notifications, and
   [generate the integration URL](/help/generate-integration-url). You'll be
   able to configure which branches you'll receive notifications from, and
   whether to exclude notifications from private repositories.

1. On your repository's web page, go to **Settings**. Select **Webhooks**,
   and click **Add webhook**. GitHub may prompt you for your password.

1. Set **Payload URL** to the URL generated above. Set **Content type**
   to `application/json`. Select the [events](#filtering-incoming-events)
   you'd like to be notified about, and click **Add Webhook**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/github/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

- [GitHub's webhook events documentation][github-webhook-events]

- [Zulip GitHub Actions integration](/integrations/doc/github-actions)

{!webhooks-url-specification.md!}

[github-webhook-events]: https://docs.github.com/en/webhooks-and-events/webhooks/webhook-events-and-payloads
