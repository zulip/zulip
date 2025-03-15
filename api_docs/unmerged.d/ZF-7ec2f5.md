* [`PATCH /streams/{stream_id}`](/api/update-stream): Added `is_archived`
  parameter to support unarchiving archived channels. Sending a PATCH request
  with `is_archived: false` will unarchive the specified channel.
