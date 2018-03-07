For the integration based on the deprecated
[GitHub Services](https://github.com/github/github-services),
see [here](./github).

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

   {!git-webhook-url-with-branches-indented.md!}

1. Go to your repository on GitHub and click on the **Settings** tab.
   Select **Webhooks**. Click on **Add webhook**. GitHub may prompt
   you for your password.

1. Set **Payload URL** to the URL constructed above. Set **Content type**
   to `application/json`. Select the events you would like to receive
   notifications for, and click **Add Webhook**.

{!congrats.md!}

![](/static/images/integrations/github_webhook/001.png)
