Get Zulip notifications for Stripe events!

1. {!create-stream.md!}

1. {!create-bot-construct-url-indented.md!}

1. On your Stripe Dashboard, click on **Developers** on the left
   sidebar. Click on **Webhooks**, and click on **+ Add endpoint**.

1. Set **URL to be called** to the URL constructed above. Select
   the event types you would like to be notified about, and click
   **Add endpoint**.

Zulip currently supports the following Stripe events:

* Charge Dispute Closed
* Charge Dispute Created
* Charge Failed
* Charge Succeeded
* Customer Created
* Customer Deleted
* Customer Subscription Created
* Customer Subsciption Deleted
* Customer Subscription Trial Will End
* Invoice Payment Failed
* Order Payment Failed
* Order Payment Succeeded
* Order Updated
* Transfer Failed
* Transfer Paid

!!! tip ""
    To set up different topics for different events, create separate
    webhooks for those events, customizing the URL stream and topic
    for each.

{% if 'http:' in external_uri_scheme %}

!!! tip ""
    Note that Stripe will only accept HTTPS webhooks!

{% endif %}

{!congrats.md!}

![](/static/images/integrations/stripe/001.png)
