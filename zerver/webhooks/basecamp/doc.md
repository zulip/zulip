# Zulip Basecamp integration

Receive notifications about Basecamp events in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your project on Basecamp, and toggle the **Settings** menu in
   the top right corner. Click on **Set up webhooks**, and then select
   **Add a new webhook**.

1. Set **Payload URL** to the URL generated above. Select the
   [events](#filtering-incoming-events) you'd like to be notified about,
   and toggle the checkbox under **Enable this webhook**. Finally, click
   **Add this webhook**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/basecamp/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
