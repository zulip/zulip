* [`GET /messages`](/api/get-messages),
  [`POST /message/flags/narrow`](/api/update-message-flags-for-narrow): Added
  a new enum value `date` for the `anchor` parameter. When using the
  `date` value for the `anchor` parameter, clients also need to set
  the new `anchor_date` parameter in ISO 8601 format. This allows to
  anchor the request to the message sent closest to the specified
  date in the `anchor_date` parameter.
