For the integration based on the deprecated
[GitHub Services](https://github.com/github/github-services),
see [here](./github).

1. {!create-stream.md!}

2. {!create-bot-construct-url-indented.md!}

3. {!git-webhook-url-with-branches-indented.md!}

4. Next, go to your repository page and click **Settings**:
   ![](/static/images/integrations/github_webhook/001.png)

5. From there, select **Webhooks**:

    ![](/static/images/integrations/github_webhook/002.png)

6. Click **Add webhook**.

    ![](/static/images/integrations/github_webhook/003.png)

7. Authorize yourself and configure your webhook.

8. In the **Payload URL** field, enter the URL constructed above.

9. Then, set **Content type** to `application/json`.

10. Next, select the actions that you want to result in a Zulip
    notification and click **Add Webhook**.

{!congrats.md!}

![](/static/images/integrations/github_webhook/004.png)
