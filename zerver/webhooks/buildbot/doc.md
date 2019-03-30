Get Zulip notifications for your Buildbot builds!

1. {!create-stream.md!}

1. {!create-a-bot-indented.md!}

1. Edit the Buildbot configuration file to add a new Zulip reporter
 ([or follow steps listed here](http://docs.buildbot.net/latest/manual/configuration/reporters.html#zulipstatuspush)):

        from buildbot.plugins import reporters

        zs = reporters.ZulipStatusPush(endpoint='your-organization@zulipchat.com',
                                       token='API_key', stream='stream_to_post_in')
        c['services'].append(zs)

{!congrats.md!}
![](/static/images/integrations/buildbot/001.png)
