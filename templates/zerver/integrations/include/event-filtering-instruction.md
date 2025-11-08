You will be able to configure which of the following
{{ integration_display_name }} events trigger notifications:

{% set comma = joiner(", ") %}

{% for event_type in all_event_types -%} {{- comma() -}} `{{ event_type }}` {%- endfor %}
