import re
import urllib
from typing import Optional

from django.conf import settings
from django.http import HttpRequest

from zerver.lib.upload import get_public_upload_root_url
from zerver.models import Realm, UserProfile


def get_subdomain(request: HttpRequest) -> str:
    # The HTTP spec allows, but doesn't require, a client to omit the
    # port in the `Host` header if it's "the default port for the
    # service requested", i.e. typically either 443 or 80; and
    # whatever Django gets there, or from proxies reporting that via
    # X-Forwarded-Host, it passes right through the same way.  So our
    # logic is a bit complicated to allow for that variation.
    #
    # For both EXTERNAL_HOST and REALM_HOSTS, we take a missing port
    # to mean that any port should be accepted in Host.  It's not
    # totally clear that's the right behavior, but it keeps
    # compatibility with older versions of Zulip, so that's a start.

    host = request.get_host().lower()
    return get_subdomain_from_hostname(host)


def get_subdomain_from_hostname(host: str) -> str:
    m = re.search(rf"\.{settings.EXTERNAL_HOST}(:\d+)?$", host)
    if m:
        subdomain = host[: m.start()]
        if subdomain in settings.ROOT_SUBDOMAIN_ALIASES:
            return Realm.SUBDOMAIN_FOR_ROOT_DOMAIN
        return subdomain

    for subdomain, realm_host in settings.REALM_HOSTS.items():
        if re.search(rf"^{realm_host}(:\d+)?$", host):
            return subdomain

    return Realm.SUBDOMAIN_FOR_ROOT_DOMAIN


def is_subdomain_root_or_alias(request: HttpRequest) -> bool:
    return get_subdomain(request) == Realm.SUBDOMAIN_FOR_ROOT_DOMAIN


def user_matches_subdomain(realm_subdomain: str, user_profile: UserProfile) -> bool:
    return user_profile.realm.subdomain == realm_subdomain


def is_root_domain_available() -> bool:
    if settings.ROOT_DOMAIN_LANDING_PAGE:
        return False
    return not Realm.objects.filter(string_id=Realm.SUBDOMAIN_FOR_ROOT_DOMAIN).exists()


def is_static_or_current_realm_url(url: str, realm: Optional[Realm]) -> bool:
    assert settings.STATIC_URL is not None
    split_url = urllib.parse.urlsplit(url)
    split_static_url = urllib.parse.urlsplit(settings.STATIC_URL)

    # The netloc check here is important to correctness if STATIC_URL
    # does not contain a `/`; see the tests for why.
    if split_url.netloc == split_static_url.netloc and url.startswith(settings.STATIC_URL):
        return True

    # HTTPS access to this Zulip organization's domain; our existing
    # HTTPS protects this request, and there's no privacy benefit to
    # using camo in front of the Zulip server itself.
    if (
        realm is not None
        and split_url.netloc == realm.host
        and f"{split_url.scheme}://" == settings.EXTERNAL_URI_SCHEME
    ):
        return True

    # Relative URLs will be processed by the browser the same way as the above.
    if split_url.netloc == "" and split_url.scheme == "":
        return True

    # S3 storage we control, if used, is also static and thus exempt
    if settings.LOCAL_UPLOADS_DIR is None:
        # The startswith check is correct here because the public
        # upload base URL is guaranteed to end with /.
        public_upload_root_url = get_public_upload_root_url()
        assert public_upload_root_url.endswith("/")
        if url.startswith(public_upload_root_url):
            return True

    return False
