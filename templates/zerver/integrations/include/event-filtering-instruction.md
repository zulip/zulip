Below are the events, to filter triggering notifications, that the
{{ integration_display_name }} bot supports:

{% set comma = joiner(", ") %}

{% for event_type in all_event_types -%} {{- comma() -}} `{{ event_type }}` {%- endfor %}
