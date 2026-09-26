* `POST /bots`: For incoming-webhook and embedded bots, sending
  `config_data` with unknown keys now returns an HTTP 400 error.
  Previously, such entries were silently written to `BotConfigData`
  and ignored.
