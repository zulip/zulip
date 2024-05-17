Get GitHub notifications in Zulip!

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

    You can refer to GitHub's documentation for [webhook events](https://docs.github.com/en/webhooks-and-events/webhooks/webhook-events-and-payloads).

    {!git-webhook-url-with-branches.md!}

1. Go to your repository on GitHub and click on the **Settings** tab.
   Select **Webhooks**. Click on **Add webhook**. GitHub may prompt
   you for your password.

1. Set **Payload URL** to the URL constructed above. Set **Content type**
   to `application/json`. Select the events you would like to receive
   notifications for, and click **Add Webhook**.

{!congrats.md!}

![](/static/images/integrations/github/001.png)

See also the [GitHub Actions integration](/integrations/doc/github-actions).
