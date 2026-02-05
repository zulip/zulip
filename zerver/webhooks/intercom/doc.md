# Zulip Intercom integration

Get Intercom notifications in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to **Settings** in your Intercom account, and click on
   **Integrations** in the left sidebar. Click on **Developer Hub**,
   and click **New app**.

1. Set **App name** to a name of your choice, such as `Zulip`. Set
   **Workspace** to the Intercom workspace of your choice, and click
   **Create app**.

1. From the app's dashboard, click on **Webhooks** in the left sidebar. Set
   **endpoint URL** to the URL generated above. Select the topics you'd
   like to be notified about, and click **Save**. You should receive a test
   message.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/intercom/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

* [Intercom doc on Webhooks](https://developers.intercom.com/docs/webhooks/setting-up-webhooks)

{!webhooks-url-specification.md!}
