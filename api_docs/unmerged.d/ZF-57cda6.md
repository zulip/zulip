* [`PATCH /streams/{stream_id}`](/api/update-stream): Added support for updating
folder to which the channel belongs.

* [`GET /events`](/api/get-events): `value` field in `stream/update` events can
have `null` when channel is removed from a folder.
