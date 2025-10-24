* [`GET /users/me/subscriptions`](/api/get-subscriptions),
  [`GET /streams`](/api/get-streams), [`GET /events`](/api/get-events),
  [`POST /register`](/api/register-queue): Added `can_create_topic_group`
  field which is a [group-setting value](/api/group-setting-values) describing
  the set of users with permissions to create new topics in the channel.
* [`POST /users/me/subscriptions`](/api/subscribe),
  [`PATCH /streams/{stream_id}`](/api/update-stream): Added `can_create_topic_group`
  parameter to support setting and changing the user group whose members can create
  new topics in the specified channel.
