In the URL field, enter:

`{{ external_uri_scheme }}bot_email:bot_api_key@{{ external_api_path_subdomain }}{{ integration_url }}`

Make sure to replace the `@` in the bot's email address with `%40`,
as {{ integration_display_name }}'s website will incorrectly refuse
to parse a username containing a `@`.

Replace `bot_email` in the above URL with the email address of the
bot you created, and replace `bot_api_key` with the API key of the
bot.
