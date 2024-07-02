# Zulip Slack integration

Get Zulip notifications from Slack for messages on your team's
public channels!

See also the [Slack-compatible webhook](/integrations/doc/slack_incoming).

{start_tabs}
1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}
   Refer the [Channel Mapping section](#channel-mapping) for options and
   directions on mapping your Slack channels to Zulip channels.

1. Create a new [Slack app][slack_app_link] and open it.

1. Navigate to the "OAuth & Permissions" menu, scroll down to the "Scopes"
   section and make sure "Bot Token Scopes" includes:
   `channels:read`, `channels:history`, `users:read`, `eomji:read`,
   `team:read`, `users:read`, `users:read.email`.
   > *Note: If you worry about the scopes that we're asking, refer to [Slack APIs used](#slack-apis-used) section to see the list of Slack APIs that we use.*

1. Next, scroll to the "OAuth Tokens for Your Workspace" section in the
   same menu and click **Install to Workspace**.

1. The **Bot User OAuth Token** should be available now. Please note it down
   and add `&slack_app_token=BOT_OAUTH_TOKEN` to the end of the URL you've just
   generated in step 3. Your webhook url should now look like this:

        {{ api_url }}{{ integration_url }}?api_key=abcdefgh&stream=123
        &slack_app_token=xoxb-123123123-123123123-XXXXXXXXX

1. Go to the **Event Subscriptions** menu, toggle **Enable Events** on and
   enter your webhook url in the **Request URL** field.

1. Still in the same menu, scroll down to the **Subscribe to bot events**,
   **Add Bot User Event** and select the event `message.channels`.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/slack/001.png)

### Channel Mapping
If you'd like to map Slack channels to different topics within the same
channel, add `&channels_map_to_topics=1` to the end of the URL. Note that
this should be used instead of specifying a topic in the URL. If a topic
is specified in the URL, then it will be prioritized over the channel to
topic mapping.

If you'd like to map Slack channels to different channels, add
`&channels_map_to_topics=0` to the end of the URL. Make sure you create
channels for all your public Slack channels *(see step 1)*, and that the
name of each channel is the same as the name of the Slack channel it maps
to. Note that in this case, the channel to channel mapping will be
prioritized over the channel specified in the URL.

### Slack APIs used

- https://api.slack.com/events/message.channels, this event is used with Event
   API to get Slack messages.
- https://api.slack.com/methods/users.info, this end point is used to get
   the username of each sender. The basic payload only include user_id
- https://api.slack.com/methods/conversations.info, this API is used to get
   the channel name of each message. The basic payload only include channel_id

[slack_app_link]: https://api.slack.com/apps
