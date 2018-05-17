Get Zulip notifications from Slack for messages on your team's
public channels!

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

    If you'd like to map Slack channels to different topics within
    Zulip, append `&channels_map_to_topics=1` to the above URL.

    If you'd like to map Slack channels to different streams within
    Zulip, append `&channels_map_to_topics=0` to the above URL. Make
    sure you create streams for all your public Slack channels and that
    the name of a given stream is the same as the name of the Slack
    channel it maps to.

1. Go to this URL: <https://my.slack.com/services/new/outgoing-webhook>,
   and click **Add Outgoing WebHooks integration**.

1. Scroll down and configure the **Channel** and **Trigger Word(s)**
   options as appropriate. Set **URL(s)** to the URL constructed above,
   and click **Save Settings**.

{!congrats.md!}

![](/static/images/integrations/slack/001.png)
