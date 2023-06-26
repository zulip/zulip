Construct the URL for the {{ integration_display_name }}
bot using the bot's API key and email address:

`{{ external_url_scheme }}bot_email:bot_api_key@{{ api_url_scheme_relative }}{{ integration_url }}`

Modify the parameters of the URL above, where `bot_email` is
the bot's URL-encoded email address and `bot_api_key` is the
bot's API key.  To URL-encode the email address, you just need
to replace `@` in the bot's email address with `%40`.
