# Zulip Mention integration

Get Mention notifications within Zulip via Zapier!

{start_tabs}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. Go to your Mention feed, and click on your profile in the top-right
   corner. Select **Settings**, click on **Integrations**, and select
   the **Zapier** integration.

1. Click **Explore Mention on Zapier**. Search for "webhooks" in
   the search bar, and click on **Webhooks by Zapier**. Look for
   **Add Webhook posts for new Mentions**, and click on
   **Use this Zap**. Click **Create this Zap**.

1. Follow the on-screen steps to link your Mention account to Zapier.
   Select your Mention **Account ID** and **Alert** when prompted.

1. Follow the on-screen steps to set up **Webhooks by Zapier POST**.
   When prompted, set **URL** to the URL constructed above, and set
   **Payload Type** to **JSON**. After **Test this Step**, click
   **Finish**.

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/mention/001.png)

### Related documentation

{!webhooks-url-specification.md!}
