To filter the events that trigger the notifications, you can append either
(or both) `&only_events=["an_event","another_event"]` or
`&exclude_events=["an_event","another_event"]`
with an arbitrary number of events to the URL.

Below is a list of events that {{ integration_display_name }} bot support:

`{{ all_event_types }}`

Note that you can also use unix-style wildcards like `*` to include
multiple events (E.g., `test*` matches events every event that starts with
`test`).
