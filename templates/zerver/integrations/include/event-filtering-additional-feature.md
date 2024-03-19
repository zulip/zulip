### Filtering incoming events

The {{ integration_display_name }} integration supports filtering for
the following events:

{% set comma = joiner(", ") %}

{% for event_type in all_event_types -%} {{- comma() -}} `{{ event_type }}` {%- endfor %}
