See your Teamcity build status in Zulip!

{!create-stream.md!}

{!create-bot-construct-url.md!}

Next, install the
[tcWebHooks plugin](https://github.com/tcplugins/tcWebHooks/releases)
onto your Teamcity server. Follow the plugin instructions in your
Teamcity documentation, or refer to [the online Teamcity documentation][1].

[1]: https://confluence.jetbrains.com/display/TCD9/Installing+Additional+Plugins

Next, in your Teamcity project overview page, click the **Webhooks**
tab, and add a new project webhook. Enter the URL you created
earlier.

Uncheck all **Trigger on Events** options, and check
**Trigger when build is Successful** and **Trigger when build Fails**.
Optionally, check **Only trigger when build changes from Failure to Success**
and **Only trigger when build changes from Success to Failure**.

Set the Payload Format to **JSON** and save your webhook.

![](/static/images/integrations/teamcity/001.png)

{!congrats.md!}

![](/static/images/integrations/teamcity/002.png)

**Personal Builds**

When a user runs a personal build, if Zulip can map their Teamcity
username to a Zulip user, that Zulip user will receive a private
message with the result of their personal build.

![](/static/images/integrations/teamcity/003.png)
