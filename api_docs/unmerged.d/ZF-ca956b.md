**Feature level ZF-ca956b**

* `PATCH /bots/{bot_id}`: The response now includes an entry only for
  each parameter that the request actually modified, using the
  parameter's current post-update value. Previously, some fields were
  always included with the bot's current database value regardless of
  whether the request touched them, and `service_interface`,
  `service_payload_url`, and `config_data` echoed the request values
  verbatim (or `null` when not sent). `config_data` now reflects the
  bot's merged configuration after the update, not just the keys sent
  in the request. The response also now includes the bot's new `email`
  when the request changed `short_name`.
