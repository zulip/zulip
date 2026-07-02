**Feature level ZF-fcf0cf**

* [`POST /messages`](/api/send-message): Added `message_url` and
  `message_link` fields to the response. `message_url` is a URL linking
  directly to the sent message; `message_link` is a Markdown link to it,
  of the form `[#channel > topic @ 💬](url)`, or the plain URL when there
  is no suitable text label (direct messages, or a channel whose name is
  omitted from the URL).
