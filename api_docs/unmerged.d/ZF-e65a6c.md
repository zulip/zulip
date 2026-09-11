* [`POST /users/me/subscriptions`](/api/subscribe),
  [`POST /channels/create`](/api/create-channel),
  [`PATCH /streams/{stream_id}`](/api/update-stream): Added the
  `PERMISSION_DENIED` error code (HTTP status 403), returned when a
  channel name collides with an existing channel the user cannot
  access, so that the channel's name and whether it is private or
  archived are not revealed. Previously these requests returned an
  error that named the conflicting channel: a `BAD_REQUEST` (HTTP
  status 400) on [`POST /users/me/subscriptions`](/api/subscribe), and
  `CHANNEL_ALREADY_EXISTS` (HTTP status 409) on
  [`POST /channels/create`](/api/create-channel) and
  [`PATCH /streams/{stream_id}`](/api/update-stream).
