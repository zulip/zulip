Zulip supports both Git and Mercurial notifications from
Bitbucket. This integration is for the old-style Bitbucket
webhooks used by Bitbucket Enterprise.

{!create-channel.md!}

The integration will use the default channel `commits` if no
channel is supplied in the hook; you still need to create the
channel even if you are using this default.

Next, from your repository's web page, go to the **Administration**
page and choose **Hooks** on the left-hand side. Choose the **POST**
hook from the list presented and click **Add hook**.

{!webhook-url-with-bot-email.md!}

{!git-append-branches.md!}

By default, notifications are sent to the `commits` channel. To
send notifications to a different channel, append
`?stream=channel_name` to the URL.

{!congrats.md!}

![](/static/images/integrations/bitbucket/002.png)
