* `POST /bots`: For incoming webhook bots, the integration to associate
  with the bot is now specified as the `integration_id` key of the
  `config_data` parameter, instead of the `service_name` parameter,
  which is now ignored for this bot type.
