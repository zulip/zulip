You can choose to be notified whenever certain events are triggered
on Stripe by adding a webhook to your Stripe account.

{!create-stream.md!}

Next, on your {{ settings_html|safe }}, create a Stripe bot.

Add a webhook to your Stripe account by going to **Your account** >
**Account settings** > **Webhooks** > **Add Endpoint**.

{!webhook-url-with-bot-email.md!}

{!append-topic.md!}

{!append-stream-name.md!}

{% if 'http:' in external_uri_scheme %}
    Note that Stripe will only accept HTTPS webhooks!
{% endif %}

![](/static/images/integrations/stripe/001.png)

To set up different topics for different events, create separate
webhooks for those events, customizing the URL stream and topic
for each.

![](/static/images/integrations/stripe/003.png)

{!congrats.md!}

![](/static/images/integrations/stripe/002.png)

You will now receive notifications for the events you have chosen.
Zulip currently supports the following events:

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
