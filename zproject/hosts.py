from django.conf import settings
from django_hosts import host, patterns

# Compatibility scaffold for a staged migration to django-hosts.
# Requests that do not match a host pattern continue using ROOT_URLCONF.
host_pattern_list = [
    host(r"", "urls", name="default"),
]

if settings.SOCIAL_AUTH_SUBDOMAIN is not None:
    host_pattern_list.append(host(settings.SOCIAL_AUTH_SUBDOMAIN, "urls", name="social-auth"))

if settings.SELF_HOSTING_MANAGEMENT_SUBDOMAIN is not None:
    host_pattern_list.append(
        host(settings.SELF_HOSTING_MANAGEMENT_SUBDOMAIN, "urls", name="self-hosting-management")
    )

# Keep this last: it matches any subdomain and would swallow reserved hosts above.
host_pattern_list.append(host(r"[\w-]+", "urls", name="wildcard"))

host_patterns = patterns("zproject", *host_pattern_list)
