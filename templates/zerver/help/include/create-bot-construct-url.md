Next, on your {{ settings_html|safe }}, create a bot for
{{ integration_display_name }}. Construct the URL for the
{{ integration_display_name }} bot using the bot API key and stream name:

{!webhook-url.md!}

Modify the parameters of the URL above, where `api_key` is the API key
of your Zulip bot, and `stream` is the stream name you want the
notifications sent to.
