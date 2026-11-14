* [`GET /users/me/subscriptions`](/api/get-subscriptions),
  [`GET /streams`](/api/get-streams), [`GET /events`](/api/get-events),
  [`POST /register`](/api/register-queue): Added
  `message_content_allowed_in_email_notifications` field which
  will indicate whether message content will be included in email
  notifications sent for messages in the channel.
* [`POST /users/me/subscriptions`](/api/subscribe),
  [`PATCH /streams/{stream_id}`](/api/update-stream): Added
  `message_content_allowed_in_email_notifications` to support
  setting whether message content will be included in email
  notifications sent for messages in the channel.
