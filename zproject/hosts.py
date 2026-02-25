from django.conf import settings
from django_hosts import host, patterns

# Compatibility scaffold for a staged migration to django-hosts.
# Requests that do not match a host pattern continue using ROOT_URLCONF.
host_pattern_list = [
    host(r"", "root_urls", name="default"),
]

if settings.SOCIAL_AUTH_SUBDOMAIN is not None:
    host_pattern_list.append(
        host(settings.SOCIAL_AUTH_SUBDOMAIN, "auth_subdomain_urls", name="social-auth")
    )

if settings.SELF_HOSTING_MANAGEMENT_SUBDOMAIN is not None:
    host_pattern_list.append(
        host(
            settings.SELF_HOSTING_MANAGEMENT_SUBDOMAIN,
            "self_hosting_management_subdomain_urls",
            name="self-hosting-management",
        )
    )

# Keep this last: it matches any subdomain and would swallow reserved hosts above.
host_pattern_list.append(host(r"[\w-]+", "realm_urls", name="wildcard"))

host_patterns = patterns("zproject", *host_pattern_list)
