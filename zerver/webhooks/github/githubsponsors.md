Get GitHub Sponsors notifications in Zulip!

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-integration-url.md!}

    You can refer to GitHub's documentation for [webhook events](https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads#sponsorship).

1. Go to your profile on GitHub and click on **Sponsors dashboard**.
   Select **Webhooks**. Click on **Add webhook**. GitHub may prompt
   you for your password.

1. Set **Payload URL** to the URL constructed above. Set **Content type**
   to `application/json` and click **Create webhook**.

{!congrats.md!}

![](/static/images/integrations/githubsponsors/001.png)

See also the [GitHub integration](/integrations/doc/github).
