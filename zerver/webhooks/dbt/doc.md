# Zulip DBT integration

Get notifications about DBT cloud job runs in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. From your DBT Dashboard, navigate to **Account settings** by clicking on
    your account from the left side panel.

1. Select **Notification Settings**, go to the **Webhooks** section, and
    click **Create webhook**.

1. In the panel that opens, enter the following details:

     * Set **Webhook name** to a name of your choice, such as `Zulip`.
     * Select the **Events** and **Jobs** you want to receive notifications for.
     * Set **Endpoint** as the URL generated above.

1. Click **Test Endpoint** to send a test notification to your Zulip
    organization, and if it's successful, click **Save**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/dbt/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation
- [Create a webhook subscription in DBT](https://docs.getdbt.com/docs/deploy/webhooks#create-a-webhook-subscription)
- [DBT's webhooks documentation](https://docs.getdbt.com/docs/deploy/webhooks)
{!webhooks-url-specification.md!}
