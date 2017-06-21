```
ZULIP_USER = "{{ integration_name }}-bot@example.com"
ZULIP_API_KEY = "0123456789abcdef0123456789abcdef"
{% if api_site_required %}ZULIP_SITE = "{{ external_api_uri_subdomain }}"{% endif %}
```
