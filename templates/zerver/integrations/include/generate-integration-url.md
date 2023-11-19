Generate the URL for your {{ integration_display_name }} integration,
with the stream (and topic) you want notifications sent to, by [viewing
the bot you created](/help/view-your-bots) and clicking the **link**
(<i class="fa fa-link"></i>) icon on the bot's profile card.

The generated URL will be something like:

{!webhook-url.md!}

*To manually construct the URL for an incoming webhook integration,
see [the webhook URLs specification][incoming-webhook-urls].*

{% if all_event_types is defined %}

{!event-filtering-instruction.md!}

{% endif %}

[incoming-webhook-urls]: /api/incoming-webhooks-overview#urls
