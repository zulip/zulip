To filter the events that trigger the notifications, you can append
either `&only_events=["event_a","event_b"]` or `&exclude_events=["event_a","event_b"]`
(or both, with different events) to the URL with an arbitrary number of supported events.

Below are the events that {{ integration_display_name }} bot supports:

{% set comma = joiner(", ") %}

{% for event_type in all_event_types -%} {{- comma() -}} `{{ event_type }}` {%- endfor %}

Note that you can also use UNIX-style wildcards like `*` to include
multiple events. E.g., `test*` matches every event that starts with
`test`.
