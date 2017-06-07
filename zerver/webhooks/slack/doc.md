Get notifications from Slack for messages on your team's public channels!

There are two ways in which you may want to receive a notification:

- Slack Channel to a single Zulip stream with different topics
- Multiple Zulip streams for multiple Slack channels

If you want a single Zulip stream to receive notifications from Slack then
first create your desired stream and subscribe all interested parties to
this stream. We recommend the name `{{ integration_name }}`.

{!create-bot-construct-url.md!}

By default, Slack Channels map to different topics. To use multiple
Zulip streams for multiple Slack channels, you can add
`&channels_map_to_topics=0` at the end of your webhook URL.

Go to the following URL: <https://api.slack.com>

Next, under the category of App features click on
**Legacy custom integrations**.

![](/static/images/integrations/slack/001.png)

Now, click on **Outgoing Webhooks** under **Custom Integrations**.

![](/static/images/integrations/slack/002.png)

Then click the hyperlink **outgoing webhook integration** which can be found
in the page.

![](/static/images/integrations/slack/003.png)

Next, click the **Add Outgoing Webhook integration** button.

![](/static/images/integrations/slack/004.png)

Now, under `Integration Settings,` fill in the channel you'd like to get your
notifications from.

Then fill in
`{{ external_api_uri_subdomain }}/v1/external/slack?api_key=abcdefgh&stream=slack&channels_map_to_topics=1`
as your URL.

![](/static/images/integrations/slack/005.png)

Finally, save your settings.

In case you want your Slack channels mapped to multiple Zulip streams, you have
to change the parameter `channels_map_to_topics=1` to `channels_map_to_topics=0`
in your URL.

The resulting URL will be
`{{ external_api_uri_subdomain }}/v1/external/slack?api_key=abcdefgh&stream=slack&channels_map_to_topics=0`

{!congrats.md!}

![](/static/images/integrations/slack/006.png)

**This integration is not created by, affiliated with, or supported by Slack
Technologies, Inc.**
