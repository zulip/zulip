### Filtering incoming events

The {{ integration_display_name }} integration supports
[filtering][event-filters] for the following events:

{% set comma = joiner(", ") %}

{% for event_type in all_event_types -%} {{- comma() -}} `{{ event_type }}` {%- endfor %}

[event-filters]: /api/incoming-webhooks-overview#only_events-exclude_events
