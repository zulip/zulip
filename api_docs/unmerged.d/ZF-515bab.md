**Feature level ZF-515bab**

* [`DELETE /users/me/subscriptions`](/api/unsubscribe): The server now
  sends a Notification Bot direct message to users who have been
  unsubscribed from one or more channels by another user. Self-
  unsubscribes and unsubscribed bots do not receive these notifications.

* [`DELETE /users/me/subscriptions`](/api/unsubscribe): Added the
  `send_messages_to_removed_subscribers` parameter, which determines
  whether the server sends the Notification Bot direct messages
  introduced above to users who were unsubscribed by this request.

* [`DELETE /users/me/subscriptions`](/api/unsubscribe): Added
  `messages_sent_to_removed_subscribers` to the response, which is only
  present if `send_messages_to_removed_subscribers` was `true` in the
  request.

* [`POST /register`](/api/register-queue): Renamed
  `max_bulk_new_subscription_messages` to `max_bulk_subscription_messages`,
  reflecting that the cap now also applies to the
  `send_messages_to_removed_subscribers` parameter on
  [`DELETE /users/me/subscriptions`](/api/unsubscribe).
