Zulip supports both Git and Mercurial notifications from
Bitbucket. This integration is for the new-style Bitbucket
webhooks used by the Bitbucket SAAS service.

For the old-style Bitbucket webhooks used by Bitbucket Enterprise,
click [here](./bitbucket).

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}
   {!git-webhook-url-with-branches-indented.md!}

1. On your repository's web page, click on **Settings**. Select
   **Webhooks**, and click **Add webhook**.

1. Set **URL** to the URL constructed above. Set **Title** to a
   title of your choice, such as `Zulip`. Check the **Active** checkbox,
   and click **Save**.

{!congrats.md!}

![](/static/images/integrations/bitbucket/003.png)
