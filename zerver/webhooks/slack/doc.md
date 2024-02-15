Get Zulip notifications from Slack for messages on your team's
public channels!

See also the [Slack-compatible webhook](/integrations/doc/slack_incoming).

1. {!create-stream.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

    If you'd like to map Slack channels to different topics within the same
    stream, add `&channels_map_to_topics=1` to the end of the URL. Note that
    this should be used instead of specifying a topic in the URL. If a topic
    is specified in the URL, then it will be prioritized over the channel to
    topic mapping.

    If you'd like to map Slack channels to different streams, add
    `&channels_map_to_topics=0` to the end of the URL. Make sure you create
    streams for all your public Slack channels *(see step 1)*, and that the
    name of each stream is the same as the name of the Slack channel it maps
    to. Note that in this case, the channel to stream mapping will be
    prioritized over the stream specified in the URL.

1. Go to <https://my.slack.com/services/new/outgoing-webhook>
   and click **Add Outgoing WebHooks integration**.

1. Scroll down and configure the **Channel** and/or **Trigger Word(s)**
   options as appropriate. Set **URL(s)** to the URL constructed above,
   and click **Save Settings**.

{!congrats.md!}

![](/static/images/integrations/slack/001.png)
