# Forward Slack messages into Zulip

Forward messages sent to your Slack workspace's public channels into Zulip!

This integration lets you choose how to organize your Slack messages in Zulip.
You can:

- Send messages from each Slack channel into a **matching Zulip channel**.
- Send messages from each Slack channel into a **matching Zulip topic**.
- Send all Slack messages into a **single Zulip topic**.

If you'd like to forward messages in both directions (Slack to Zulip and Zulip
to Slack), please see [separate instructions][6] for how to set this up.

If you are looking to quickly move your Slack integrations to Zulip, check out
[Zulip's Slack-compatible incoming webhook][1].

!!! warn ""

    Using [Slack's legacy Outgoing Webhook service][5] is no longer
    recommended. Follow these instructions to switch to the new
    [Slack Events API][3].

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

    To send messages from each Slack channel into a **matching Zulip channel**,
    open the **Where to send notifications** dropdown and select **Matching
    Zulip channel**.

    To send messages from each Slack channel into a **matching Zulip topic**,
    open the **Topics to use** dropdown, and select **Topics named after Slack
    channels**.

    To send all Slack messages into a **single Zulip topic**, open the **Topics
    to use** dropdown, and select **Send all notifications to a single topic**.

1. *(optional)* If you're setting up a [Slack bridge][6] to forward Zulip messages
   into your Slack workspace, replace the value of the `?api_key=` parameter in
   the **integration URL** you generated with the API key of the **Generic bot**
   you're using for the Slack bridge.

1. Create a new [Slack app][4], and open it. Navigate to the **OAuth
   & Permissions** menu, and scroll down to the **Scopes** section.

1. Make sure **Bot Token Scopes** includes `channels:history`, `channels:read`,
   and `users:read`. If you're setting up a [bidirectional bridge][6], make sure
   to also include the `chat:write` scope.

    !!! tip ""

        See the [required bot token scopes](#required-bot-token-scopes)
        section for details about these scopes.

1. Scroll to the **OAuth Tokens** section in the same menu, and click **Install
   to Workspace**.  Grant the app permission to access your workspace
   by clicking **Allow** when prompted.

1. You will immediately see a **Bot User OAuth Token**. Copy it and add it
   to the end of your **integration URL** as `&slack_app_token=BOT_OAUTH_TOKEN`.

1. Go to the **Event Subscriptions** menu, toggle **Enable Events**, and enter
   your updated **integration URL** in the **Request URL** field.

1. In the same menu, scroll down to the **Subscribe to bot events**
   section, and click on **Add Bot User Event**. Select the
   `message.channels` event.

1. Add the bot as an app to the Slack channels you'd like to receive
   notifications from.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/slack/001.png)

### Required bot token scopes

- `channels:history` is required by Slack's Event API's
  [message.channels](https://api.slack.com/events/message.channels) event. This
  is used to send new messages from Slack to Zulip.

- `channels:read` is required for Slack's
  [conversations.info](https://api.slack.com/methods/conversations.info)
  endpoint. This is used to get the name of the Slack channel a message came
  from.

- For a [bidirectional bridge][6] setup, the `chat:write` is also required for
  Slack's
  [chat.postMessage](https://docs.slack.dev/reference/methods/chat.postMessage/)
  method. This is used to send new messages from Zulip to Slack.

- `users:read` is required to call
  Slack's [users.info](https://api.slack.com/methods/users.info) endpoint. This
  is used to get the name of the Slack message's sender.

### Related documentation

- [Forward messages Slack <-> Zulip][6] (both directions)

- [Slack Events API documentation][3]

- [Slack Apps][4]

- [Zulip's Slack-compatible incoming webhook][1]

{!webhooks-url-specification.md!}

[1]: /integrations/slack_incoming
[2]: /help/create-a-channel
[3]: https://api.slack.com/apis/events-api
[4]: https://api.slack.com/apps
[5]: https://api.slack.com/legacy/custom-integrations/outgoing-webhooks
[6]: https://github.com/zulip/python-zulip-api/blob/main/zulip/integrations/bridge_with_slack/README.md
