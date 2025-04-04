# Zulip Gogs integration

Receive Gogs notifications in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-with-branch-filtering.md!}

1. Go to your repository on Gogs and click on **Settings**. Select
   **Webhooks** on the left sidebar, and click **Add Webhook**.
   Select **Gogs**.

1. Set **Payload URL** to the URL generated above. Set **Content type**
   to `application/json`. Select the [events](#filtering-incoming-events)
   you would like to receive notifications for, and click **Add Webhook**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/gogs/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
