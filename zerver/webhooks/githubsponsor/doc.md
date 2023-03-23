Get GitHub Sponsor notifications in Zulip!

1. {!create-stream.md!}

1. {!create-bot-construct-url.md!}

 You can refer to GitHub's documentation for [webhook events] (https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads#sponsorship)

1. Go to your profile on GitHub and click on the **your sponsor** tab.
   Select **Webhooks**. Click on **Add webhook**. GitHub may prompt
   you for your password.

1. Set **Payload URL** to the URL constructed above. Set **Content type**
   to `application/json` and click **Add Webhook**.

{!congrats.md!}
![](/static/images/integrations/githubsponsor/001.png)
