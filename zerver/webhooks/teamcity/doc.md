# Zulip TeamCity integration

Get Zulip notifications for your TeamCity builds!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Install the [tcWebHooks plugin][1] onto your TeamCity server. Follow
   the plugin instructions in your TeamCity documentation, or refer to
   [the online TeamCity documentation][2].

1. Go to your TeamCity **Overview** page. Select the **Project** or
   **Build** you'd like to receive notifications about, and click on the
   **WebHooks** tab. Click **Add project WebHooks** for a **Project**,
   or click **Add build WebHooks** for a **Build**. Select **Click to
   create new WebHook for this project/build**.

1. Set **URL** to the URL generated above, and set **Payload Format** to
   **Legacy Webhook (JSON)**. Untoggle all **Trigger on Events** options,
   and toggle **Trigger when build is Successful** and **Trigger when
   build Fails**. You may also toggle the options **Only trigger when
   build changes from Failure to Success** and **Only trigger when build
   changes from Success to Failure** if you'd like. Click **Save**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/teamcity/001.png)

### Personal Builds

When a user runs a personal build in TeamCity, if Zulip can map their
TeamCity username to a Zulip user (by matching it to a Zulip user's
email address or full name), then that Zulip user will receive a direct
message with the result of their personal build.

### Related documentation

- [tcWebHooks plugin][1]

- [TeamCity plugin installation documentation][2]

{!webhooks-url-specification.md!}

[1]: https://github.com/tcplugins/tcWebHooks/releases
[2]: https://www.jetbrains.com/help/teamcity/installing-additional-plugins.html
