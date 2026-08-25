# Zulip dbt integration

Get notifications about dbt cloud job runs in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

    If you'd like your notification messages to link to your dbt job
    runs, make sure you include the [**dbt Access URL**][dbt Access URLs]
    when generating the integration URL.

1. From your dbt Dashboard, navigate to **Account settings**. Select
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

- [dbt's webhooks documentation](https://docs.getdbt.com/docs/deploy/webhooks)
- [dbt Access URLs][dbt Access URLs]
{!webhooks-url-specification.md!}

[dbt Access URLs]: https://docs.getdbt.com/docs/cloud/about-cloud/access-regions-ip-addresses#api-access-urls
