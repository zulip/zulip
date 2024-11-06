# Zulip GitHub Sponsors integration

Get GitHub Sponsors notifications in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your profile on GitHub, and click on **Sponsors dashboard**.
   Select **Webhooks**, and click **Add webhook**. GitHub may prompt
   you for your password.

1. Set **Payload URL** to the URL generated above. Set **Content type**
   to `application/json`, and click **Create webhook**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/githubsponsors/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

- [GitHub's webhook events documentation][github-webhook-events]

- [Zulip GitHub integration](/integrations/doc/github).

{!webhooks-url-specification.md!}

[github-webhook-events]: https://docs.github.com/en/webhooks-and-events/webhooks/webhook-events-and-payloads
