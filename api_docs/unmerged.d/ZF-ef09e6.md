* [`POST /messages`](/api/send-message), [`PATCH
  /messages/{message_id}`](/api/update-message): The logic for
  producing a `STREAM_WILDCARD_MENTION_NOT_ALLOWED` or
  `TOPIC_WILDCARD_MENTION_NOT_ALLOWED` error now also checks the
  channel-level `can_mention_many_users_group` setting. Previously,
  only the realm-level setting was consulted.
* Added `can_mention_many_users_group` as a channel-level permission
  setting that grants additional users beyond those permitted by the
  organization-level `can_mention_many_users_group` the ability to use
  wildcard mentions (`@all`, `@everyone`, `@channel`, `@topic`) in a
  specific channel. This field is included in channel and subscription
  objects returned by [`GET /streams`](/api/get-streams), [`GET
  /users/me/subscriptions`](/api/get-subscriptions), and [`POST
  /register`](/api/register-queue), and can be set via [`POST
  /users/me/subscriptions`](/api/subscribe), [`POST
  /channels/create`](/api/create-channel), and [`PATCH
  /streams/{stream_id}`](/api/update-stream).
