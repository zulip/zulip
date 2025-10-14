# Zulip DBT integration

Get notifications about DBT cloud job runs in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. From your DBT Dashboard, navigate to **Account settings**. Select
   **Notification Settings**, go to the **Webhooks** section, and
   click **Create webhook**.

1. Set **Webhook name** to a name of your choice, such as `Zulip`. Select
    the **Events** and **Jobs** you want to receive notifications for,
    and set **Endpoint** to the URL generated above. Click **Save**.

1. Click **Test Endpoint** to send a test notification to
    your Zulip organization.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/dbt/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

- [DBT's webhooks documentation](https://docs.getdbt.com/docs/deploy/webhooks)
{!webhooks-url-specification.md!}
