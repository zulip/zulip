Get notifications from Slack for messages on your team's public channels!

There are two ways in which you may want to receive a notification:

- Slack Channel to a single Zulip stream with different topics
- Multiple Zulip streams for multiple Slack channels

### Single stream with different topics

{!create-stream.md!}

{!create-bot-construct-url.md!}

If you'd like to receive notifications to a single stream with
different topics for different Slack channels, append
`&channels_map_to_topics=1` to the above URL.

### Multiple Zulip streams for multiple Slack channels

First, create streams for all of your Slack channels. Make sure that
the name of a given stream is the same as the name of the Slack channel
it maps to.

{!create-bot-construct-url.md!}

If you'd like your Slack channels to be mapped to multiple Zulip
streams, append `&channels_map_to_topics=0` to the above URL.

### Configuring the webhook

Go to the following URL: <https://api.slack.com>

Next, under the category of App features click on
**Legacy custom integrations**.

![](/static/images/integrations/slack/001.png)

Now, click on **Outgoing Webhooks** under **Custom Integrations**.

![](/static/images/integrations/slack/002.png)

Then click the hyperlink **outgoing webhook integration** which can be
found in the page.

![](/static/images/integrations/slack/003.png)

Next, click the **Add Outgoing Webhook integration** button.

![](/static/images/integrations/slack/004.png)

Now, under `Integration Settings`, fill in the channel you'd like
to get your notifications from.

Then fill in the URL created above as your URL. Finally, save your
settings.

![](/static/images/integrations/slack/005.png)

{!congrats.md!}

![](/static/images/integrations/slack/006.png)

**This integration is not created by, affiliated with, or supported by Slack
Technologies, Inc.**
