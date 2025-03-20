* [`GET /users/me/subscriptions`](/api/get-subscriptions),
  [`GET /streams`](/api/get-streams), [`GET /events`](/api/get-events),
  [`POST /register`](/api/register-queue): Added `can_unsubscribe_group`
  field to Stream and Subscription objects.
* [`POST /users/me/subscriptions`](/api/subscribe),
  [`PATCH /streams/{stream_id}`](/api/update-stream): Added `can_unsubscribe_group`
  parameter for setting the user group whose members can unsubscribe themselves from channel.
* [`DELETE /users/me/subscriptions`](/api/unsubscribe): Unsubscription is allowed for organization administrators,
  users who can administer the channel or remove other subscribers, and members of the channel's `can_unsubscribe_group`.
