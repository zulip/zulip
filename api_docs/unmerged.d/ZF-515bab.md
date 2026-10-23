* [`DELETE /users/me/subscriptions`](/api/unsubscribe): Added
  `send_messages_to_removed_subscribers` boolean parameter, which
  determines whether the server should attempt to send a direct
  message, from Notification Bot, to other users who were
  unsubscribed from one or more channels by the current user.
  Previously, no notification messages were sent when a user was
  unsubscribed from a channel by another user.

* [`DELETE /users/me/subscriptions`](/api/unsubscribe): Added
  `messages_sent_to_removed_subscribers` boolean field to the response,
  which is only present if the new `send_messages_to_removed_subscribers`
  parameter was `true` in the request.

* [`POST /register`](/api/register-queue): Renamed the
  `max_bulk_new_subscription_messages` field in the response to
  `max_bulk_subscription_messages` as this limit now applies to
  notification messages sent when another user is subscribed or
  unsubscribed to one or more channels by the current user.
