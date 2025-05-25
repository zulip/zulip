Open `{{ config_file_path}}` with your favorite editor, and change the
following lines to specify the email address and API key for your
{{ integration_display_name }} bot:

```
ZULIP_USER = "{{ integration_name }}-bot@{{ display_host }}"
ZULIP_API_KEY = "0123456789abcdef0123456789abcdef"
ZULIP_SITE = "{{ zulip_url }}"
```
