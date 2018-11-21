Get Zulip notifications for Stripe events!

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

1. On your Stripe Dashboard, click on **Developers** on the left
   sidebar. Click on **Webhooks**, and click on **+ Add endpoint**.

1. Set **URL to be called** to the URL constructed above. Select
   the event types you would like to be notified about, and click
   **Add endpoint**.

1. [Optional] In Zulip, add a
   [linkification filter](/help/add-a-custom-linkification-filter) with
   **Pattern** `(?P<id>cus_[0-9a-zA-Z]+)` and **URL format string**
   `https://dashboard.stripe.com/customers/%(id)s`.

Zulip currently supports Stripe events for Charges, Customers, Discounts,
Sources, Subscriptions, Files, Invoices and Invoice items.

{% if 'http:' in external_uri_scheme %}

!!! tip ""
    Note that Stripe will only accept HTTPS webhooks!

{% endif %}

{!congrats.md!}

![](/static/images/integrations/stripe/001.png)
