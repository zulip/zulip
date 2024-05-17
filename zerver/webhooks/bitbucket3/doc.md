Zulip supports both Git and Mercurial notifications from
Bitbucket. This integration is for the the new-style Bitbucket
webhooks used by Bitbucket Server.

For the old-style Bitbucket webhooks used by Bitbucket Enterprise,
click [here](./bitbucket), and for the new-style webhooks used by
Bitbucket Cloud (SAAS service) click [here](./bitbucket2).

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

    {!git-webhook-url-with-branches.md!}

1. On your repository's web page, click on **Settings**. Select
   **Webhooks**, and click **Add webhook**.

1. Set **Title** to a title of your choice, such as `Zulip`. Set **URL**
   to the URL constructed above, and check the **Active** checkbox. Select
   the **Triggers** you'd like to be notified about, and click **Save**.

{!congrats.md!}

![](/static/images/integrations/bitbucket/004.png)
