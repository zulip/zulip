On your {{ settings_html|safe }}, create a bot for
{{ integration_display_name }}.

Next, open
`integrations/{{ integration_name }}/zulip_{{ integration_name }}_config.py`
with your favorite editor, and change the following lines to specify the
email address and API key for your {{ integration_display_name }} bot:

{!zulip-config.md!}
