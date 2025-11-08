# Zulip Pivotal integration

Get Zulip notifications for the stories in your Pivotal Tracker project!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. From your Pivotal project's **Settings** page, click on **Webhooks**.

1. Under **Activity Web Hook**, provide the URL generated above.
   Choose version 5 (`v5`) of the API. Click **Add**.

    !!! warn ""

         **Note:** Zulip supports both version 3 and version 5, but version
         5 contains more information and allows Zulip to format more useful messages.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/pivotal/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
