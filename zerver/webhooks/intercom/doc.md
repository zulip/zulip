# Zulip Intercom integration

Get Intercom notifications in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to **Settings** in your Intercom account, and click on
   **Developers** in the left sidebar. Click on **Developer Hub**,
   and click **New app**.

1. Set **App name** to a name of your choice, such as `Zulip`. Set
   **Workspace** to the Intercom workspace of your choice, and click
   **Create app**.

1. Click on **Webhooks** in the left sidebar. Set **Your request
   endpoint URL** to the URL generated above. Select the topics you'd
   like to be notified about, and click **Save**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/intercom/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
