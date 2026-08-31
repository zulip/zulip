* `PATCH /bots/{bot_id}`: Sending `service_interface` or
  `service_payload_url` for a bot that is not an outgoing-webhook
  bot now returns an HTTP 400 error. Previously,
  `service_payload_url` triggered an unhandled HTTP 500 error for
  default and incoming-webhook bots and was silently accepted for
  embedded bots.
* `PATCH /bots/{bot_id}`: The `config_data` parameter is now only
  accepted for incoming-webhook and embedded bots; sending it for
  other bot types returns an HTTP 400 error. Previously, entries
  were written to `BotConfigData` for any bot type, though only
  these two types use them.
