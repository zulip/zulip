[Generate the URL][generate-url] for your {{ integration_display_name }}
integration.

The generated URL will be something like:

{!webhook-url.md!}

*To manually construct the URL for an incoming webhook integration,
see [the webhook URLs specification][incoming-webhook-urls].*

{% if all_event_types is defined %}

{!event-filtering-instruction.md!}

{% endif %}

[generate-url]: /help/generate-integration-url
[incoming-webhook-urls]: /api/incoming-webhooks-overview#urls
