# Zulip AppOptics integration

Get Zulip notifications for your SolarWinds AppOptics (formerly Librato) alerts!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your AppOptics homepage, and click on **Settings**. Select
   **Metric Settings**, click **Notification Services**, and select
   **Webhooks**.

1. Set **Title** to a title of your choice, such as `Zulip`. Set **URL**
   to the URL generated above, and click **Add**.

!!! tip ""

    When you create a new **Alert**, you can enable this webhook from the
    **Notification Services** tab.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/appoptics/001.png)

### Related documentation

{!webhooks-url-specification.md!}
