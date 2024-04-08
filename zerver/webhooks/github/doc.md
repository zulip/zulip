Get GitHub notifications in Zulip!

{start_tabs}

1. {!create-stream.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your repository on GitHub and click on the **Settings** tab.
   Select **Webhooks**. Click on **Add webhook**. GitHub may prompt
   you for your password.

1. Set **Payload URL** to the URL constructed above. Set **Content type**
   to `application/json`. Select the events you would like to receive
   notifications for, and click **Add Webhook**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/github/001.png)

See also the [GitHub Actions integration](/integrations/doc/github-actions).

### Related documentation

{!webhooks-url-specification.md!}
