* [`GET /users/me/subscriptions`](/api/get-subscriptions),
  [`GET /streams`](/api/get-streams), [`GET /events`](/api/get-events),
  [`POST /register`](/api/register-queue): Added `can_resolve_topics_group`
  which is a [group-setting value](/api/group-setting-values) describing the
  set of users with permissions to resolve topics in the channel.
* [`POST /users/me/subscriptions`](/api/subscribe),
  [`PATCH /streams/{stream_id}`](/api/update-stream): Added `can_resolve_topics_group`
  which is a [group-setting value](/api/group-setting-values) describing the
  set of users with permissions to resolve topics in the channel.
