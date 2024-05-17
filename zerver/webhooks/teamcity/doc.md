Get Zulip notifications for your TeamCity builds!

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

1. Install the [tcWebHooks plugin](https://github.com/tcplugins/tcWebHooks/releases)
   onto your TeamCity server. Follow the plugin instructions in your
   TeamCity documentation, or refer to [the online TeamCity documentation][1].

1. Go to your TeamCity **Overview** page. Select the **Project** or **Build**
   you'd like to receive notifications about, and click on the **WebHooks** tab.
   If you'd like to configure webhooks for a **Project**, click on
   **Add project WebHooks**. If you'd like to configure webhooks for a specific
   **Build**, click on **Add build WebHooks**. Click on
   **Click to create new WebHook for this project/build**.

1. Set **URL** to the URL constructed above. Set **Payload Format** to
   **Legacy Webhook (JSON)**. Uncheck all **Trigger on Events** options,
   and check **Trigger when build is Successful** and **Trigger when build Fails**.

1. Optionally, check **Only trigger when build changes from Failure to Success**
   and **Only trigger when build changes from Success to Failure**.

1. Click **Save**.

[1]: https://confluence.jetbrains.com/display/TCD9/Installing+Additional+Plugins

{!congrats.md!}

![](/static/images/integrations/teamcity/001.png)

**Personal Builds**

When a user runs a personal build, if Zulip can map their TeamCity
username to a Zulip user (by comparing it with the Zulip user's email
address or full name), that Zulip user will receive a direct message
with the result of their personal build.

![](/static/images/integrations/teamcity/002.png)
