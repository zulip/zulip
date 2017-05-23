# Unread message synchronization

In general displaying unread counts for all streams and topics may require
downloading an unbounded number of messages. Consider a user who has a muted
stream or topic and has not read the backlog in a month; to have an accurate
unread count we would need to load all messages this user has received in the
past month. This is inefficient for web clients and even more for mobile
devices.

We work around this by including a list of unread message ids in the initial
state grouped by recipient and subject. This data is included in the
`unread_msgs` key if both update_message_flags and message are required in the
register call.

```
[
    [
        {
            'display_recipient': 'general',
            'recipient_id': 54,
            'subject': 'lunch',
        },
        [400, 823]
    ]
]
```

Three event types are required to correctly maintain the `unread_msgs`. New
messages can be created without the unread flag by the `message` event type.
The unread flag can be added and removed by the `update_message_flags` event,
and the subject of unread messages can be updated by the `update_message` event
type.
