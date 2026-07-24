# Zulip Gong integration

Get notifications about completed Gong calls in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. From your Gong dashboard, navigate to **Admin center > Settings >
   Ecosystem > Automation rules**, and click **+ Add rule** to create a
   new automation rule for sending call data to Zulip.

1. Configure the [rule filters][gong-call-search] to specify which calls
   should trigger the webhook, and click **Save**.

1. In the **Action** dropdown, **Fire webhook** should be selected by
   default. Enter the webhook URL generated above, and select **URL
   includes key** for the authentication method.

1. Enter a name (e.g., "Zulip") and description for the automation rule.

1. Test the automation by clicking **Test now** with the preselected call data.
   Or you can choose to **Select a different call** for the test.

1. Enable the rule by toggling the **Rule Status** switch.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/gong/001.png)


### Related documentation

- [Gong's webhook documentation][gong-webhook-rule]

- [Filtering Gong calls][gong-call-search]

{!webhooks-url-specification.md!}

[gong-webhook-rule]: https://help.gong.io/docs/create-a-webhook-rule
[gong-call-search]: https://help.gong.io/docs/search-for-calls
