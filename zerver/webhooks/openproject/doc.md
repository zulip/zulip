# Zulip Open Project integration

Get Zulip notifications for new events on your **Open Project** page.

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Sign in to OpenProject and create your organization.

1. Inside your organization go to **Profile** > **Administration**.

1. Navigate to **API and Webhooks** > **Webhooks**.

1. Click on **+ Webhook** and create a new webhook with the `Payload URL` same as the URL generated above.

1. Make sure all events are enabled in the **Enabled Events** section, then click save.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/openproject/001.png)

### Related documentation

* [**OpenProject Webhook Integration**][1]

{!webhooks-url-specification.md!}

[1]: https://www.openproject.org/docs/system-admin-guide/api-and-webhooks/
