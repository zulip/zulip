* [Slack-compatible outgoing webhooks](/api/outgoing-webhook-payload#slack-compatible-format):
  Added a `command` field to the payload. When a message starts with a
  mention of the bot, the mention is now sent as `command` (transformed
  to `/My Bot`, for a bot named `My Bot`) and `text` contains only the
  remainder of the message. Previously, `text` always contained the full
  message content including the bot mention.
