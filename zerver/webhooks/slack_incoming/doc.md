Zulip can process incoming webhook messages written to work with Slack's
[incoming webhook API](https://api.slack.com/messaging/webhooks). This makes it
easy to quickly move your integrations when migrating your organization from
Slack to Zulip. See also the [Slack integration](/integrations/doc/slack) for
mirroring content from a Slack instance into Zulip.

!!! warn ""

     In the long term, the recommended approach is to use Zulip's native
     integrations, which take advantage of Zulip's topics. There may also be
     some quirks when Slack's formatting system is translated into Zulip's.

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

1. Use your new webhook URL any place that you would use a Slack webhook.

**Congratulations! You're done!**
