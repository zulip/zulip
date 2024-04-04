[Generate the URL][generate-url] for your {{ integration_display_name }}
integration.

{% if all_event_types is defined %}

{!event-filtering-instruction.md!}

{% endif %}

The generated URL will look something like this:

{!webhook-url.md!}

*To manually construct the URL for an incoming webhook integration,
see [the webhook URLs specification][incoming-webhook-urls].*

[generate-url]: /help/generate-integration-url
[incoming-webhook-urls]: /api/incoming-webhooks-overview#url-specification
