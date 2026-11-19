* [`PATCH /messages/{message_id}`](/api/update-message): Content edits
  now fail with the `EDIT_HISTORY_LIMIT_EXCEEDED` error code once a
  message's content has been edited too many times, or its edit history
  is too large. Requests that only move a message aren't affected.
