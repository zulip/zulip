Open `/usr/local/share/zulip/integrations/{{ integration_name }}/zulip_{{ integration_name }}_config.py`
with your favorite editor, and change the following lines to specify the
email address and API key for your {{ integration_display_name }} bot:

```
ZULIP_USER = "{{ integration_name }}-bot@example.com"
ZULIP_API_KEY = "0123456789abcdef0123456789abcdef"
ZULIP_SITE = "{{ api_url }}"
```
