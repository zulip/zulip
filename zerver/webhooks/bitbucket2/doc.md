Zulip supports both Git and Mercurial notifications from
Bitbucket. This integration is for the new-style Bitbucket
webhooks used by the Bitbucket SAAS service.

For the old-style Bitbucket webhooks used by Bitbucket Enterprise,
click [here](./bitbucket).

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

   {!git-webhook-url-with-branches-indented.md!}

1. From your repository's web page, go to the **Settings**
   page and choose **Webhooks** on the left-hand side.
   Click **Add webhook**.

1. Set **URL** to the URL you created above. Remember to check the
   **active** checkbox.

    ![](/static/images/integrations/bitbucket2/001.png)

1. Click **Save**.

{!congrats.md!}

![](/static/images/integrations/bitbucket/003.png)
