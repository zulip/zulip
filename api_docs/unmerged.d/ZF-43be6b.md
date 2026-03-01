* [`GET /events`](/api/get-events), [`GET /messages`](/api/get-messages),
  [`GET /messages/{message_id}`](/api/get-message),
  [`POST /messages/flags`](/api/update-message-flags),
  [`POST /messages/flags/narrow`](/api/update-message-flags-for-narrow):
  Added `hide_link_previews` as a supported [message
  flag](/api/update-message-flags#available-flags) that can be
  toggled by the user. When set, clients should hide auto-generated
  link previews on the message for that user. Like other flags, it
  appears in the message's `flags` array and in `update_message_flags`
  events. The flag can be set on any message, whether or not it
  currently has a link preview.
