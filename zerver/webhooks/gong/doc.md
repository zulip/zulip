# Zulip Gong integration

Get notifications about completed Gong calls in Zulip!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. From your Gong dashboard, navigate to **Admin center > Settings >
   Ecosystem > Automation rules**.

1. Click **+ Add rule** to create a new automation rule for sending call
   data to Zulip.

    * Configure the [rule filters][gong-call-search] to specify which calls
       should trigger the webhook, and click **SAVE**.

    * In the **Action** dropdown, **Fire webhook** is selected by default, with
       the **URL includes key** authentication option. Enter the webhook URL
       generated above.

    * Enter a rule name (e.g., "Zulip integration") and a description.

1. Test the call by clicking **Test now**, and check for a success message
   in green near the top of the screen, and a notification in Zulip.

1. Enable the rule by toggling the **Rule Status** switch.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/gong/001.png)


### Related documentation

- [Gong's webhook rule instructions][gong-webhook-rule]

- [Filtering Gong calls][gong-call-search]

{!webhooks-url-specification.md!}

[gong-webhook-rule]: https://help.gong.io/docs/create-a-webhook-rule
[gong-call-search]: https://help.gong.io/docs/search-for-calls
