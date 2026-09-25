**Feature level ZF-f9de78**

* [`POST /scheduled_messages`](/api/create-scheduled-message): Added the
  `split_message_contents` parameter, for scheduling a message composed as
  one and split into several parts as a single group of scheduled messages
  that deliver in order at the same time. When used, the response contains
  `scheduled_message_ids` instead of `scheduled_message_id`. The `content`
  parameter is now optional, but exactly one of `content` and
  `split_message_contents` must be provided.
* [`GET /scheduled_messages`](/api/get-scheduled-messages), [`POST
  /register`](/api/register-queue), and the `scheduled_messages` events:
  Scheduled message objects now include a `split_group_id` field, shared by
  every part of a split scheduled message and `null` otherwise.
