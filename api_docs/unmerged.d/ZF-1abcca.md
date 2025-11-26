* `PATCH /realm`, [`POST /register`](/api/register-queue),
  [`GET /events`](/api/get-events): Added `can_unsubscribe_group`
  realm setting, which is a [group-setting value](/api/group-setting-values)
  describing the set of users who have permission to unsubscribe themselves
  from all channels in the organization.
* [`GET /users/me/subscriptions`](/api/get-subscriptions),
  [`GET /streams`](/api/get-streams), [`GET /events`](/api/get-events),
  [`POST /register`](/api/register-queue): Added `can_unsubscribe_group`
  field to Stream and Subscription objects.
* [`POST /users/me/subscriptions`](/api/subscribe),
  [`PATCH /streams/{stream_id}`](/api/update-stream): Added `can_unsubscribe_group`
  parameter for setting the user group whose members can unsubscribe themselves from channel.
* [`DELETE /users/me/subscriptions`](/api/unsubscribe): Unsubscription is allowed for organization administrators,
  users who can administer the channel or remove other subscribers, and members of the channel's `can_unsubscribe_group`.
