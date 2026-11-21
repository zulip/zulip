* [`POST /register`](/api/register-queue), [`GET /events`](/api/get-events),
  [`GET /streams`](/api/get-streams),
  [`GET /streams/{stream_id}`](/api/get-stream-by-id),
  [`GET /users/me/subscriptions`](/api/get-subscriptions): Added
  `default_color` field to channel objects, containing the color that
  should be assigned to new subscribers of the channel, or `null` if the
  channel has no configured default color.

* [`PATCH /streams/{stream_id}`](/api/update-stream): Added
  `default_color` parameter that lets organization administrators set or
  clear the default color new subscribers to the channel will be
  assigned.
