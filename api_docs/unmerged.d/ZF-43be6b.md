**Feature level RANDOM**

- [`POST /messages/flags`](/api/update-message-flags),
  [`POST /messages/flags/narrow`](/api/update-message-flags-for-narrow):
  Added `hide_link_previews` as a supported [message
  flag](/api/update-message-flags#available-flags) that can be
  toggled by the user. When set, clients should hide
  auto-generated link previews on the message for that user.
