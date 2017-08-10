Zulip supports both Git and Mercurial notifications from
Bitbucket. This integration is for the new-style Bitbucket
webhooks used by the Bitbucket SAAS service.

For the old-style Bitbucket webhooks used by Bitbucket Enterprise,
click [here](./bitbucket).

{!create-stream.md!}

The integration will use the default stream `bitbucket` if
no stream is supplied in the hook; you still need to create
the stream even if you are using this default.

{!create-bot-construct-url.md!}

{!git-webhook-url-with-branches.md!}

Next, from your repository's web page, go to the **Settings**
page and choose **Webhooks** on the left-hand side.

Click **Add webhook**, set **URL** to the URL you created above.
Remember to click the **'active'** checkbox.

Click **Save**.

{!congrats.md!}

![](/static/images/integrations/bitbucket/003.png)
