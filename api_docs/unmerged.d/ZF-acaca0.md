* [`POST /scheduled_messages`](/api/create-scheduled-message),
  [`PATCH /scheduled_messages/{scheduled_message_id}`](/api/update-scheduled-message):
  Added `split_message_on_send` parameter, for scheduling a message
  that the server delivers as several messages, split wherever two or
  more consecutive blank lines appear outside a code block.
* [`GET /scheduled_messages`](/api/get-scheduled-messages), [`POST
  /register`](/api/register-queue), [`GET /events`](/api/get-events):
  Scheduled message objects now include a `split_message_on_send`
  field.
