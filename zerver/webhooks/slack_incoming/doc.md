This beta Zulip integration supports for processing incoming webhook
messages written to work with Slack's [incoming webhook
API](https://api.slack.com/messaging/webhooks).

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

1. Use your new webhook URL any place that you would use a Slack webhook.

{!congrats.md!}

Where possible, we prefer to create native Zulip integrations that
make optimal use of Zulip's topics and don't require translating
formatting, but this is a useful stopgap, especially for getting
messages from third-party vendors that only offer a Slack integration
(with no generic outgoing webhook API).

This integration, by its nature, involves a somewhat complex
translation between Slack's formatting system and Zulip's.  We
appreciate [feedback and bug reports](/help/contact-support) on any
cases where the resulting Zulip formatting is poor, so that we can
either improve the formatting or add an appropriate native integration.

See also the [Slack notifications](/integrations/doc/slack)
integration for mirroring content from a Slack instance into Zulip.
