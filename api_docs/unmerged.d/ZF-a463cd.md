* [`GET /streams`](/api/get-streams),
  [`POST /users/me/subscriptions`](/api/subscribe),
  [`PATCH /streams/{stream_id}`](/api/update-stream),
  [`GET /events`](/api/get-events): Stream objects now
  include the `can_access_stream_topics_group` integer,
  which specifies the ID of the user group that has
  access to all the topics in a stream.
