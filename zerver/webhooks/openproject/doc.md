# Zulip OpenProject integration

Get Zulip notifications for your **OpenProject** activities!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. From your OpenProject organization, click on your user profile icon,
   choose **Administration**, select **API and Webhooks**, and navigate to  
   the **Webhooks** tab from the left panel.

1. Click on **+ Webhook**. Enter a name of your choice for the webhook,
   set `Payload URL` to the URL generated above, and ensure the webhook is
   enabled.

1. Select the events and projects you want to receive notifications for, and
   click **Create**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/openproject/001.png)

### Related documentation

* [**OpenProject Webhook Integration**][1]

{!webhooks-url-specification.md!}

[1]: https://www.openproject.org/docs/system-admin-guide/api-and-webhooks/#webhooks
