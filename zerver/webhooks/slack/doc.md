# Zulip Slack integration

Get Zulip notifications from Slack for messages on your team's
public channels!

See also the [Slack-compatible webhook](/integrations/doc/slack_incoming).

{start_tabs}

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Create a new [Slack app][slack_app_link], and open it. Navigate to
   the **OAuth & Permissions** menu, and scroll down to the **Scopes**
   section.

1. Make sure **Bot Token Scopes** includes `channels:read`,
   `channels:history`, `users:read`, `emoji:read`, `team:read`,
   `users:read`, and `users:read.email`.

    !!! warn ""
        **Note**: If you're concerned about the scopes specified above,
        see [Slack's Events API documentation][events_api_doc_link]
        for more context

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

### Configuration options

*  If you'd like to map Slack channel names to message topics in Zulip,
   add `&channels_map_to_topics=1` to the generated URL above. Note that
   this should be used instead of specifying a topic when generating the
   URL. If a topic is specified in the URL, then it will be prioritized
   over the Slack channel to Zulip topic mapping.

*  If you'd like to map Slack channels to Zulip channels, add
   `&channels_map_to_topics=0` to the generated URL above. Make sure you
   create Zulip channels for all your public Slack channels *(see step 1
   above)*, and that the name of each Zulip channel is the same as the
   name of the Slack channel it maps to. Note that in this case, the
   Slack channel to Zulip channel mapping will be prioritized over any
   Zulip channel specified when generating the URL.

### Related documentation

- [Slack Events API documentation][events_api_doc_link]

- [Slack Apps][slack_app_link]

{!webhooks-url-specification.md!}

[events_api_doc_link]: https://api.slack.com/apis/events-api

[slack_app_link]: https://api.slack.com/apps
