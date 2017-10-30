This webhook is based on the deprecated
[GitHub Services](https://github.com/github/github-services).

{!create-stream.md!}

The integration will use the default stream `commits`
if no stream is supplied in the hook; you still need to create
the stream even if you are using this default.

Next, go to your repository page and click **Settings**:

![](/static/images/integrations/github/001.png)

From there, select **Webhooks & Services**:

![](/static/images/integrations/github/002.png)

To find the Zulip hook, you have to click on **Configure services**.

![](/static/images/integrations/github/003.png)

Select **Zulip** from the list of service hooks. Fill in the API key
and email address for your bot that you created earlier and check
the **"active"** checkbox. Specify
`{{ api_url }}/v1/external/github` as the
**Alternative endpoint**. You can optionally supply the Zulip stream
(the default is `commits`) and restrict Zulip notifications to a
specified set of branches.

Further configuration is possible. By default, commits traffic
(pushes, commit comments), GitHub issues traffic, and pull requests
are enabled. You can exclude certain types of traffic via the checkboxes.
If you want commit traffic, issue traffic, and pull requests to go to
different places, you can use the **Commit Stream** and **Issue Stream**
overrides; otherwise, it is safe to leave these fields blank and just
have it default to the **Stream** setting.

Click the **Update settings** button to complete the configuration:

![](/static/images/integrations/github/004.png)

{!congrats.md!}

![](/static/images/integrations/github/005.png)
