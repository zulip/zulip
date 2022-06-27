Receive Gitea notifications in Zulip!

1. {!create-stream.md!}

1. {!create-bot-construct-url.md!}

    {!git-webhook-url-with-branches.md!}

1. Go to your repository on Gitea and click on **Settings**. Select
   **Webhooks** on the left sidebar, and click **Add Webhook**.
   Select **Gitea**.

1. Set **Payload URL** to the URL constructed above. Set **Content type**
   to `application/json`. Select the events you would like to receive
   notifications for, and click **Add Webhook**.

{!congrats.md!}

![](/static/images/integrations/gitea/001.png)
