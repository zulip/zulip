For the integration based on the deprecated
[GitHub Services](https://github.com/github/github-services),
see [here](./github).

{!create-stream.md!}

{!create-bot-construct-url.md!}

{!git-webhook-url-with-branches.md!}

Next, go to your repository page and click **Settings**:

![](/static/images/integrations/github_webhook/001.png)

From there, select **Webhooks**:

![](/static/images/integrations/github_webhook/002.png)

Click **Add webhook**.

![](/static/images/integrations/github_webhook/003.png)

Authorize yourself and configure your webhook.

In the **Payload URL** field, enter the URL constructed above.

Then, set **Content type** to `application/json`.

Next, select the actions that you want to result in a Zulip
notification and click **Add Webhook**.

{!congrats.md!}

![](/static/images/integrations/github_webhook/004.png)
