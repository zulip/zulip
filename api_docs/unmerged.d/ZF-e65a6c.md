* [`POST /users/me/subscriptions`](/api/subscribe),
  [`POST /channels/create`](/api/create-channel),
  [`PATCH /streams/{stream_id}`](/api/update-stream): Added the
  `PERMISSION_DENIED` error code (HTTP status 403), returned when a
  channel name collides with an existing channel the user cannot
  access, instead of revealing the channel's existence. For
  [`POST /users/me/subscriptions`](/api/subscribe), this replaces the
  previous `BAD_REQUEST` error (HTTP status 400) whose message named
  the conflicting channel.
