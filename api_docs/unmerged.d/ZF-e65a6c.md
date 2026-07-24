* [`POST /users/me/subscriptions`](/api/subscribe),
  [`POST /channels/create`](/api/create-channel),
  [`PATCH /streams/{stream_id}`](/api/update-stream): Added the
  `PERMISSION_DENIED` error code, returned when a channel name collides
  with an existing channel the user cannot access, instead of revealing
  the channel's existence.
