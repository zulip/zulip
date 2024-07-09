# Zulip Stripe integration

Get Zulip notifications for Stripe events!

{start_tabs}

1. {!create-channel.md!}

1. {!create-an-incoming-webhook.md!}

1. {!generate-webhook-url-basic.md!}

1. On your Stripe Dashboard, select **Developers** on the left
   sidebar. Select **Webhooks**, and click on **+ Add endpoint**.

1. Set the **URL to be called** to the URL generated above. Select the
   [event types](#filtering-incoming-events) you would like to be notified
   about, and click **Add endpoint**.

1. [Add a new linkifier](/help/add-a-custom-linkifier) in your Zulip
   organization. Set the pattern to `(?P<id>cus_[0-9a-zA-Z]+)` and the URL
   template to `https://dashboard.stripe.com/customers/{id}`. This step
   creates links to Stripe customers in Zulip messages and topics.

{% if 'http:' in external_url_scheme %}

!!! tip ""

    Note that Stripe will only accept HTTPS webhooks!

{% endif %}

{end_tabs}

{!congrats.md!}

![](/static/images/integrations/stripe/001.png)

{!event-filtering-additional-feature.md!}

### Related documentation

{!webhooks-url-specification.md!}
