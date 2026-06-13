* [`GET /attachments`](/api/get-attachments), [`GET /events`](/api/get-events):
  Previously, the `messages` field in `Attachment` was array of
  objects containing `id` and `date_sent` properties. That has been replaced
  by a `message_ids` field, which is a flat array of message IDs.
