* [Message formatting](/api/message-formatting#global-times): Invalid
  timestamp formats in `<time:...>` syntax are now rendered as escaped
  literal text (e.g., `&lt;time:invalid date&gt;`) instead of a `<span>`
  element with class `timestamp-error` containing an error message.
