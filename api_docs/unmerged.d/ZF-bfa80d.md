* [`POST /users/me/subscriptions`](/api/subscribe),
  [`POST /channels/create`](/api/create-channel),
  [`PATCH /streams/{stream_id}`](/api/update-stream): Added
  `can_mention_many_users_group` parameter, a
  [group-setting value](/api/group-setting-values) controlling which
  users can use wildcard mentions (e.g., `@all`, `@everyone`,
  `@channel`, `@topic`) in a channel when the number of users to be
  notified exceeds the wildcard mention threshold. This is a
  channel-level supplement to the realm-level
  `can_mention_many_users_group` setting: a user permitted by either
  setting may use wildcard mentions in the channel. Defaults to the
  `role:nobody` system group, meaning no additional users are granted
  the permission for the channel.
* [`GET /users/me/subscriptions`](/api/get-subscriptions),
  [`GET /streams`](/api/get-streams),
  [`GET /streams/{stream_id}`](/api/get-stream-by-id),
  [`GET /events`](/api/get-events),
  [`POST /register`](/api/register-queue): Added
  `can_mention_many_users_group` to channel objects, a
  [group-setting value](/api/group-setting-values) with the above
  semantics.
* [`POST /messages`](/api/send-message),
  [`PATCH /messages/{message_id}`](/api/update-message): The
  `STREAM_WILDCARD_MENTION_NOT_ALLOWED` and
  `TOPIC_WILDCARD_MENTION_NOT_ALLOWED` errors are now returned only
  when the user is not permitted by either the realm-level or the new
  channel-level `can_mention_many_users_group` setting. Previously,
  only the realm-level setting was consulted.
