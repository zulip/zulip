Get Zulip notifications from Slack for messages on your team's
public channels!

See also the [Slack-compatible webhook](/integrations/doc/slack_incoming).

1. {!create-stream.md!}

1. {!create-an-incoming-webhook.md!}

    Construct the URL for the {{ integration_display_name }}
    bot using the bot's API key:

    `{{ api_url }}{{ integration_url }}?api_key=abcdefgh`

    If you'd like to map Slack channels to different topics within the
    same stream, add `&channels_map_to_topics=1` to the end of the URL.
    This is the default behavior of the integration.

    If you'd like to map Slack channels to different streams, add
    `&channels_map_to_topics=0` to the end of the URL. Make sure you
    create streams for all your public Slack channels, and that the name
    of each stream is the same as the name of the Slack channel it maps
    to.

1. Go to <https://my.slack.com/services/new/outgoing-webhook>
   and click **Add Outgoing WebHooks integration**.

1. Scroll down and configure the **Channel** and/or **Trigger Word(s)**
   options as appropriate. Set **URL(s)** to the URL constructed above,
   and click **Save Settings**.

{!congrats.md!}

![](/static/images/integrations/slack/001.png)
