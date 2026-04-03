* [`GET /users/{user_id_or_email}/presence`](/api/get-user-presence): Added
  `slim_presence` parameter. When set to `true`, the response returns presence
  data in the modern format with `active_timestamp` and `idle_timestamp` fields,
  consistent with the format used by [`POST /users/me/presence`](/api/update-presence)
  when using `slim_presence` or `last_update_id`.
