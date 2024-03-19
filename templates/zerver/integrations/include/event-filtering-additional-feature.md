* The {{ integration_display_name }} integration supports filtering for
  the following events:

    {% set comma = joiner(", ") %}

    {% for event_type in all_event_types -%} {{- comma() -}} `{{ event_type }}` {%- endfor %}

    To filter the events that trigger the notifications, you can append
    either `&only_events=["event_a","event_b"]` or
    `&exclude_events=["event_a","event_b"]` (or both, with different
    events) to the URL you generated with an arbitrary number of
    supported events.

    Note that you can also use UNIX-style wildcards like `*` to include
    multiple events. E.g., `test*` matches every event that starts with
    `test`.
