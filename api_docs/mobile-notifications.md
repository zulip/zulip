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
  "realm_name": "Zulip Dev",
  "realm_url": "http://zulip.testserver",
  "recipient_type": "direct",
  "recipient_user_ids": [6,10,12,15],
  "sender_avatar_url": "https://secure.gravatar.com/avatar/818c212b9f8830dfef491b3f7da99a14?d=identicon&version=1",
  "sender_full_name": "aaron",
  "sender_id": 6,
  "time": 1754385290,
  "type": "message",
  "user_id": 10
}
```

- The `recipient_user_ids` field is a sorted array of all user IDs in
the direct message conversation, including both `user_id` and
`sender_id`.

**Changes**: In Zulip 12.0 (feature level 429), replaced the
`pm_users` field with `recipient_user_ids`. The old `pm_users` field
was only present for group DMs, and was a string containing a
comma-separated list of sorted user IDs.

New in Zulip 11.0 (feature level 413).

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

### Data sent to Zulip's push notifications service

Sample JSON data sent by a self-hosted server to the Zulip's push notifications service:
```json
{
  "realm_uuid": "e502dde1-74fc-44b3-9e3a-114c41ed3ea4",
  "push_requests": [
    {
      "device_id": 1,
      "http_headers": {
        "apns_priority": 10,
        "apns_push_type": "alert"
      },
      "payload": {
        "push_account_id": 10,
        "encrypted_data": "uOGQ9m8bdnLab/2Qq6WLdJnFUsU/NlX0955rF6GgpiZylQB/HSD+lrHct0KUXdCneu+fnGOuBMAGkYol+SLlbvdsnePn/f6wSvMDbm3iffcgiz2u8TywUlmQL/Q7Ruj5RSpLgEhpFitL/WjwQBtrA31vsqMHycmROju+tOhFlVjmzJmYy3o7ZQDi/YeB2Y+CnA5EuuXjckBYSjL4vi/YaEJXmeHvJ8Pk3T/WwXvo8CFZYlafiqSw0vC/2bkjPTFFAFVo/49nAUI+5Rpa90wJUVChsrkKTclOs4Ih1dNIDYr6+WoIKJTtIR9zgDg3YOkVHBZhlt7Se3i40WAs5JAb1PViMpAp2hbU36z1Qq0g90nmfRjXN9FRdAPaKlbFTT2PkEtS9wVBv9T14ufkhbOwaMLfx5iaHKw3XHoWo7Fe+0IF9ZJ77uhCZoA1kyFKDhl7AZ8K4DOvib8gsfkeAR4XXXnXVmLtAyjBhMrWYNsECo9j4UeE6M90z3xIVR8=",
        "aps": {
          "mutable-content": 1,
          "alert": {
            "title": "New notification"
          }
        }
      }
    },
    {
      "device_id": 2,
      "fcm_priority": "high",
      "payload": {
        "push_account_id": 20,
        "encrypted_data": "OzPhtLiyU1U+3ynqyTxkFt83N5GN7t3Uw8/OkCoFKFo/cu3GAzCMMbAAhPghflkrFK37SNOuxpPiL1TzPy5tQJqdSKpQrgu6cp0Y6VVA1aV/zsCDAcSABaWeaOeC5mVL+xFpmFeEbhzUaOLchbRn4kBO4m8gqDU/rAn0cKFY1F7tyCgC+fvvcczP05itDLpkwZMnrADGp3tSHFldr4iGO1pWJxFTXFFhg63UyH1FcMXKFzBPek7hLbpLsqu5OFEQv2TtDbAYdWZr1LXRqnkHTDmMd6NAdkOsVcnk31jHThFPDqaM5zDXb24hGHW79OpBnGAQWydfeChS4pC4yHWCO6ZRDqwvJX9IydS+V7S91KCl0QSToaXvgW7Q3zvHunzu7L/rw0dQQRgPM3qIOHr7gGtptkZpmKuT6icdDGgjRtgP/L0TfxdRKa37fn6nF64+HH60wLPYWOz7vZjgTrA20MrbA3ogMfhFYpwjppidFGVWjrLpk+peQjHB1sY="
      }
    }
  ]
}
```

**Changes**: New in Zulip 11.0 (feature level 413).

### Data sent to FCM

Zulip's push notifications service uses [Firebase Admin Python SDK](https://github.com/firebase/firebase-admin-python)
to access FCM.

A sample `messages` argument, which is internally used by the SDK to prepare payload for FCM,
passed to [`firebase_admin.messaging.send_each`](https://firebase.google.com/docs/reference/admin/python/firebase_admin.messaging#send_each):
```py
[
  firebase_admin.messaging.Message(
    data={
      'push_account_id': '20',
      'encrypted_data': 'OzPhtLiyU1U+3ynqyTxkFt83N5GN7t3Uw8/OkCoFKFo/cu3GAzCMMbAAhPghflkrFK37SNOuxpPiL1TzPy5tQJqdSKpQrgu6cp0Y6VVA1aV/zsCDAcSABaWeaOeC5mVL+xFpmFeEbhzUaOLchbRn4kBO4m8gqDU/rAn0cKFY1F7tyCgC+fvvcczP05itDLpkwZMnrADGp3tSHFldr4iGO1pWJxFTXFFhg63UyH1FcMXKFzBPek7hLbpLsqu5OFEQv2TtDbAYdWZr1LXRqnkHTDmMd6NAdkOsVcnk31jHThFPDqaM5zDXb24hGHW79OpBnGAQWydfeChS4pC4yHWCO6ZRDqwvJX9IydS+V7S91KCl0QSToaXvgW7Q3zvHunzu7L/rw0dQQRgPM3qIOHr7gGtptkZpmKuT6icdDGgjRtgP/L0TfxdRKa37fn6nF64+HH60wLPYWOz7vZjgTrA20MrbA3ogMfhFYpwjppidFGVWjrLpk+peQjHB1sY=',
    },
    token='push-device-token-3',
    android=firebase_admin.messaging.AndroidConfig(priority='high'),
  ),
]
```

**Changes**: New in Zulip 11.0 (feature level 413).

### Data sent to APNs

Zulip's push notifications service uses [aioapns](https://github.com/Fatal1ty/aioapns) to access APNs.

A sample `request` argument, which is internally used by the library to prepare payload for APNs,
passed to [`aioapns.APNs.send_notification`](https://github.com/Fatal1ty/aioapns/blob/96831003ec5a8986206cde77e59fdb4b5a3c4b24/aioapns/client.py):
```py
aioapns.NotificationRequest(
  apns_topic='remote_push_device_ios_app_id',
  device_token='push-device-token-1',
  message={
    'push_account_id': 10,
    'encrypted_data': 'rUNqoWOB+EQmjThJyXhDptmUrHyzSx4DPlvShzrM7XGdRVMG5qNuH0dnGQDVza9frnWNVOF3vFcuYvDnUnYRBf1j+/n1ML1K2CBnsThCGl3KJNWrKcf5fME7Q1dU2xtJ3+RAKuLtZ9y2gq6DWamui7WfQ75m1eJpYRDbbHIQEiSIZpo7X2Lie3aHkQBgE8SN5MJ6N3VM33DM6i1xGpIeWiFy+hqNloGyEI2qf6xV0SjvvkN+HbGticben4atBkAuAIKi0gIYMPyMihH26T1sEhOH3IDyO3KvaHe1NIdj0naT9RoFkN5UgdxIchXQ7qkVEjivA2E/HefpvZYlhems6TAosfJwgCMB8HuydqdImjixkugRQfugroTTG97p6xQIJSFWCOyrpuBDElI0Ale8XjmzaVo4Dbgqz5kIAhmJWtlwgJw8nt7Orr3EWUVjnIAi0nHCFObAXNShedAbyuLeC1qezqC4FZe/GOLLi4DPWgWSdk8PV5vGw9YC+XcZ38dqQogtpG7dpzMwwsqzLBmlzQ==',
    'aps': {
      'mutable-content': 1,
      'alert': {'title': 'New notification'}
    }
  },
  priority=10,
  push_type="alert",
)
```

**Changes**: New in Zulip 11.0 (feature level 413).
