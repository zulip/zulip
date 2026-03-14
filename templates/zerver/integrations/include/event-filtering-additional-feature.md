### Filtering incoming events

The {{ integration_display_name }} integration supports
[filtering][event-filters] for the following events:

{% set comma = joiner(", ") %}

{% for event_type in all_event_types -%} {{- comma() -}} `{{ event_type }}` {%- endfor %}

[event-filters]: https://zulip.readthedocs.io/en/latest/webhooks/incoming-webhooks-overview.html#only_events-exclude_events
