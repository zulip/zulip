* [`GET /attachments`](/api/get-attachments), [`GET /events`](/api/get-events):
  The `create_time` and `date_sent` fields in `attachment` objects will now
  return UNIX timestamps in seconds. Previously, these values were returned in
  milliseconds.
* [`PATCH /messages/{message_id}`](/api/update-message): The `create_time` and
  `date_sent` fields in `detached_uploads` object will now return UNIX timestamps
  in seconds. Previously, these values were returned in milliseconds.
