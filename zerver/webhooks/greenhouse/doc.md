{!create-stream.md!}

The integration will automatically use the default stream
`greenhouse` if no stream is supplied, though you will still
need to create the stream manually even though it's the
default.

{!create-bot-construct-url.md!}

Go to the account settings page of your Greenhouse account and
under **Webhooks**, add the above URL and name the integration,
Zulip.

To change the topic displayed by the bot, simply append `&topic=name`
to the end of the above URL, where `name` is your topic.

{!congrats.md!}

![](/static/images/integrations/greenhouse/000.png)
