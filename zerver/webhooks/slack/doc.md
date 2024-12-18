# Zulip Slack integration

Get Zulip notifications for messages on your team's public Slack
channels! You can choose to map each **Slack channel** either to a
**Zulip topic** or to a **Zulip channel**.

See also the [Zulip Slack incoming webhook integration][1].

!!! warn ""

    Using [Slack's legacy Outgoing Webhook service][5] is no longer
    recommended. Follow these instructions to switch to the new
    [Slack Events API][3].

{start_tabs}

1. To map each Slack channel to a Zulip topic, [create one channel][2]
   you'd like to use for Slack notifications. Otherwise, for each public
   Slack channel, [create a Zulip channel][2] with the same name.

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

    To map each Slack channel to a Zulip topic, make sure that the
    **Send all notifications to a single topic** option is disabled
    when generating the URL. Add `&channels_map_to_topics=1` to the
    generated URL.

    Otherwise, add `&channels_map_to_topics=0` to the generated URL.
    Note that any Zulip channel you specified when generating the URL
    will be ignored in this case.

1. Create a new [Slack app][4], and open it. Navigate to the **OAuth
   & Permissions** menu, and scroll down to the **Scopes** section.

1. Make sure **Bot Token Scopes** includes `channels:read`,
   `channels:history`, `emoji:read`, `team:read`, `users:read`, and
   `users:read.email`.

    !!! tip ""

        See [Slack's Events API documentation][3] for details about
        these scopes.

1. Scroll to the **OAuth Tokens for Your Workspace** section in the
   same menu, and click **Install to Workspace**.

1. The **Bot User OAuth Token** should be available now. Note it down as
   `BOT_OAUTH_TOKEN`, and add it to the end of the URL you generated
   above as: `&slack_app_token=BOT_OAUTH_TOKEN`.

1. Go to the **Event Subscriptions** menu, toggle **Enable Events**,
   and enter the URL with the bot user token in the **Request URL**
   field.

1. In the same menu, scroll down to the **Subscribe to bot events**
   section, and click on **Add Bot User Event**. Select the
   `message.channels` event.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/slack/001.png)

### Related documentation

- [Slack Events API documentation][3]

- [Slack Apps][4]

{!webhooks-url-specification.md!}

[1]: /integrations/doc/slack_incoming
[2]: /help/create-a-channel
[3]: https://api.slack.com/apis/events-api
[4]: https://api.slack.com/apps
[5]: https://api.slack.com/legacy/custom-integrations/outgoing-webhooks
