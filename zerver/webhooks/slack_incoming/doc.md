# Zulip Slack incoming webhook integration

Zulip can process incoming webhook messages written to work with Slack's
[incoming webhook API][1]. This makes it easy to quickly move your
integrations when migrating your organization from Slack to Zulip.

!!! warn ""

     **Note:** In the long term, the recommended approach is to use
     Zulip's native integrations, which take advantage of Zulip's topics.
     There may also be some quirks when Slack's formatting system is
     translated into Zulip's.

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Use the generated URL anywhere you would use a Slack webhook.

{end_tabs}

### Related documentation

- [Slack's incoming webhook documentation][1]

- [Zulip Slack integration](/integrations/doc/slack)

{!webhooks-url-specification.md!}

[1]: https://api.slack.com/messaging/webhooks
