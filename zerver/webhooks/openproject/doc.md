# Zulip OpenProject integration

Get Zulip notifications for your OpenProject work packages and projects!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. From your OpenProject organization, click on your user profile icon.
   Select **Administration** from the dropdown menu, and navigate to
   **API and Webhooks**. Select the **Webhooks** tab from the left panel,
   and click on **+ Webhook**.

1. Enter a name of your choice for the webhook, such as `Zulip`. Set
   **Payload URL** to the URL generated above, and ensure the webhook is
   enabled.

1. Select the events and projects you want to receive notifications for,
   and click **Create**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/openproject/001.png)

### Related documentation

* [**OpenProject webhook guide**][1]

{!webhooks-url-specification.md!}

[1]: https://www.openproject.org/docs/system-admin-guide/api-and-webhooks/#webhooks
