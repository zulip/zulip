# Mobile notifications

Zulip Server 11.0+ supports end-to-end encryption (E2EE) for mobile
push notifications. Mobile push notifications sent by all Zulip
servers go through Zulip's mobile push notifications service, which
then delivers the notifications through the appropriate
platform-specific push notification service (Google's FCM or Apple's
APNs). E2EE push notifications ensure that mobile notification message
content and metadata is not visible to intermediaries.

Mobile clients that have [registered an E2EE push
device](/api/register-push-device) will receive mobile notifications
end-to-end encrypted by their Zulip server.

This page documents the format of the encrypted JSON-format payloads
that the client will receive through this protocol. The same encrypted
payload formats are used for both Firebase Cloud Messaging (FCM) and
Apple Push Notification service (APNs).

## Payload examples

### New channel message

Sample JSON data that gets encrypted:
```json
{
  "channel_id": 10,
  "channel_name": "Denmark",
  "content": "@test_user_group",
  "mentioned_user_group_id": 41,
  "mentioned_user_group_name": "test_user_group",
  "message_id": 45,
  "realm_name": "Zulip Dev",
  "realm_url": "http://zulip.testserver",
  "recipient_type": "channel",
  "sender_avatar_url": "https://secure.gravatar.com/avatar/818c212b9f8830dfef491b3f7da99a14?d=identicon&version=1",
  "sender_full_name": "aaron",
  "sender_id": 6,
  "time": 1754385395,
  "topic": "test",
  "type": "message",
  "user_id": 10
}
```

- The `mentioned_user_group_id` and `mentioned_user_group_name` fields
  are only present for messages that mention a group containing the
  current user, and triggered a mobile notification because of that
  group mention. For example, messages that mention both the user
  directly and a group containing the user, these fields will not be
  present in the payload, because the direct mention has precedence.

**Changes**: New in Zulip 11.0 (feature level 413).

### New direct message

Sample JSON data that gets encrypted:
```json
{
  "content": "test content",
  "message_id": 46,
  "pm_users": "6,10,12,15",
  "realm_name": "Zulip Dev",
  "realm_url": "http://zulip.testserver",
  "recipient_type": "direct",
  "sender_avatar_url": "https://secure.gravatar.com/avatar/818c212b9f8830dfef491b3f7da99a14?d=identicon&version=1",
  "sender_full_name": "aaron",
  "sender_id": 6,
  "time": 1754385290,
  "type": "message",
  "user_id": 10
}
```

- **Group direct messages**: The `pm_users` string field is only
present for group direct messages, containing a sorted comma-separated
list of all user IDs in the group direct message conversation,
including both `user_id` and `sender_id`.

**Changes**: New in Zulip 11.0 (feature level 413).

### New group direct message

### Remove notifications

When a batch of messages that had previously been included in mobile
notifications are marked as read, are deleted, become inaccessible, or
otherwise should no longer be displayed to the user, a removal
notification is sent.

Sample JSON data that gets encrypted:
```json
{
  "message_ids": [
    31,
    32
  ],
  "realm_name": "Zulip Dev",
  "realm_url": "http://zulip.testserver",
  "type": "remove",
  "user_id": 10
}
```

[zulip-bouncer]: https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html#mobile-push-notification-service

**Changes**: New in Zulip 11.0 (feature level 413).

### Test push notification

A user can trigger [sending an E2EE test push notification](/api/e2ee-test-notify)
to the user's selected mobile device or all of their mobile devices.

Sample JSON data that gets encrypted:
```json
{
  "realm_name": "Zulip Dev",
  "realm_url": "http://zulip.testserver",
  "time": 1754577820,
  "type": "test",
  "user_id": 10
}
```

**Changes**: New in Zulip 11.0 (feature level 420).

## Future work

This page will eventually also document the formats of the APNs and
FCM payloads wrapping the encrypted content.
