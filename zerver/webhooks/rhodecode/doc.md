# Zulip RhodeCode integration

Get RhodeCode notifications in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-with-branch-filtering.md!}

1. From your repository on RhodeCode, open the **Repository Settings** tab.
    Select **Integrations**, click on **Create new integration**, and
    select **Webhook**.

1. Set **Webhook URL** to the URL generated above. Select the
    [events](#filtering-incoming-events) you would like to receive notifications
    for, and click **Submit**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/rhodecode/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
