* [`GET /events`](/api/get-events): The `reaction` events for both the `add`
  and `remove` operations now include a `message_sender_id` field, containing
  the ID of the sender of the message that was reacted to. This lets clients
  tell whether a reaction is to the current user's own message without
  fetching that message.
