# Zulip Open Project integration

Get Zulip notifications for new sign-ups on your **Open Project** page.

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. In OpenProject, click on sign in button and then create your organisation.

1. After logging in Go to **Profile** > **Administration**.

1. Click navigate to **API and Webhooks** > **Webhooks**.

1. Click on **+ Webhook** and enter Name and Payload URL same as URL generated above.

1. Scroll down and select every events in **Enabled Events**, then click save.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/openproject/001.png)

### Related documentation

* [**OpenProject Webhook Integration**][1]

{!webhooks-url-specification.md!}

[1]: https://www.openproject.org/docs/system-admin-guide/api-and-webhooks/