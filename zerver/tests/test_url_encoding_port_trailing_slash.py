from types import SimpleNamespace
from typing import cast

from django.test import override_settings

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.url_encoding import get_realm_url_with_port
from zerver.models import Realm


class UrlEncodingPortCoverageTest(ZulipTestCase):
    def test_get_realm_url_with_custom_port_added_when_trailing_slash(self) -> None:
        # Use a trailing slash so get_realm_url_with_port() exercises rstrip("/")
        realm = cast(Realm, SimpleNamespace(url="https://chat.example.com/"))
        with override_settings(APPLICATION_SERVER_CONFIG={"nginx_listen_port": 8443}):
            self.assertEqual(get_realm_url_with_port(realm), "https://chat.example.com:8443")
