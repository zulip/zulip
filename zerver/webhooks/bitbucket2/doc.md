Zulip supports both Git and Mercurial notifications from
Bitbucket. This integration is for the new-style Bitbucket
webhooks used by the Bitbucket SAAS service.

For the old-style Bitbucket webhooks used by Bitbucket Enterprise,
click [here](./bitbucket).

1. {!create-stream.md!}
   The integration will use the default stream `bitbucket` if
   no stream is supplied in the hook; you still need to create
   the stream even if you are using this default.

2. {!create-bot-construct-url-indented.md!}

3. {!git-webhook-url-with-branches-indented.md!}

4. Next, from your repository's web page, go to the **Settings**
   page and choose **Webhooks** on the left-hand side.

5. Click **Add webhook**.

6. Set **URL** to the URL you created above. Remember to check the
   **active** checkbox.

7. Click **Save**.

{!congrats.md!}

![](/static/images/integrations/bitbucket/003.png)
