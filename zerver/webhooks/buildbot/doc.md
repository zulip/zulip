Get Zulip notifications for your Buildbot builds!

!!! tip ""

    This integration requires Buildbot version 2.2.0 or higher.

1. {!create-stream.md!}

1. {!create-a-bot-indented.md!}

1. Edit the Buildbot configuration file to add a new Zulip reporter
 ([or follow the steps listed here][1]):

        from buildbot.plugins import reporters

        zs = reporters.ZulipStatusPush('{{ zulip_url }}',
                                       token='api_key',
                                       stream='{{ recommended_stream_name }}')
        c['services'].append(zs)

    When adding the new reporter, modify the code above such that `api_key`
    is the API key of your Zulip bot, and `stream` is set to the stream name
    you want the notifications sent to.

[1]: https://docs.buildbot.net/latest/manual/configuration/reporters/zulip_status.html

{!congrats.md!}

![](/static/images/integrations/buildbot/001.png)
