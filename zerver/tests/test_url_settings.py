import importlib

from django.test import TestCase, override_settings

import zproject.computed_settings as computed


class URLSettingsCompatTest(TestCase):
    # ---------- LDAP ----------
    @override_settings(AUTH_LDAP_SERVER_URL=None, AUTH_LDAP_SERVER_URI="ldap://old.example")
    def test_ldap_legacy_only(self) -> None:
        importlib.reload(computed)
        self.assertEqual(computed.AUTH_LDAP_SERVER_URL, "ldap://old.example")

    @override_settings(AUTH_LDAP_SERVER_URL="ldap://new.example", AUTH_LDAP_SERVER_URI=None)
    def test_ldap_new_only(self) -> None:
        importlib.reload(computed)
        self.assertEqual(computed.AUTH_LDAP_SERVER_URL, "ldap://new.example")

    @override_settings(
        AUTH_LDAP_SERVER_URL="ldap://new.example", AUTH_LDAP_SERVER_URI="ldap://old.example"
    )
    def test_ldap_precedence(self) -> None:
        importlib.reload(computed)
        self.assertEqual(computed.AUTH_LDAP_SERVER_URL, "ldap://new.example")

    # ---------- CAMO ----------
    # IMPORTANTE: para “legacy only”, zere CAMO_URL; para “new only”, zere CAMO_URI.
    @override_settings(CAMO_URL="", CAMO_URI="/legacy_content/")
    def test_camo_legacy_only(self) -> None:
        importlib.reload(computed)
        self.assertEqual(computed.CAMO_URL, "/legacy_content/")

    @override_settings(CAMO_URL="/external_content/", CAMO_URI="")
    def test_camo_new_only(self) -> None:
        importlib.reload(computed)
        self.assertEqual(computed.CAMO_URL, "/external_content/")

    @override_settings(CAMO_URL="/external_content/", CAMO_URI="/legacy_content/")
    def test_camo_precedence(self) -> None:
        importlib.reload(computed)
        self.assertEqual(computed.CAMO_URL, "/external_content/")

    # ---------- DEFAULT_AVATAR_URL ----------
    @override_settings(DEFAULT_AVATAR_URL=None, DEFAULT_AVATAR_URI="http://old/avatar.svg")
    def test_default_avatar_legacy_only(self) -> None:
        importlib.reload(computed)
        self.assertEqual(computed.DEFAULT_AVATAR_URL, "http://old/avatar.svg")

    @override_settings(DEFAULT_AVATAR_URL="http://new/avatar.svg", DEFAULT_AVATAR_URI=None)
    def test_default_avatar_new_only(self) -> None:
        importlib.reload(computed)
        self.assertEqual(computed.DEFAULT_AVATAR_URL, "http://new/avatar.svg")

    @override_settings(
        DEFAULT_AVATAR_URL="http://new/avatar.svg", DEFAULT_AVATAR_URI="http://old/avatar.svg"
    )
    def test_default_avatar_precedence(self) -> None:
        importlib.reload(computed)
        self.assertEqual(computed.DEFAULT_AVATAR_URL, "http://new/avatar.svg")

    # ---------- DEFAULT_LOGO_URL ----------
    @override_settings(DEFAULT_LOGO_URL=None, DEFAULT_LOGO_URI="http://old/logo.svg")
    def test_default_logo_legacy_only(self) -> None:
        importlib.reload(computed)
        self.assertEqual(computed.DEFAULT_LOGO_URL, "http://old/logo.svg")

    @override_settings(DEFAULT_LOGO_URL="http://new/logo.svg", DEFAULT_LOGO_URI=None)
    def test_default_logo_new_only(self) -> None:
        importlib.reload(computed)
        self.assertEqual(computed.DEFAULT_LOGO_URL, "http://new/logo.svg")

    @override_settings(
        DEFAULT_LOGO_URL="http://new/logo.svg", DEFAULT_LOGO_URI="http://old/logo.svg"
    )
    def test_default_logo_precedence(self) -> None:
        importlib.reload(computed)
        self.assertEqual(computed.DEFAULT_LOGO_URL, "http://new/logo.svg")

    # ---------- REALM_MOBILE_REMAP_URLS ----------
    @override_settings(REALM_MOBILE_REMAP_URLS={}, REALM_MOBILE_REMAP_URIS={"a": "b"})
    def test_realm_remap_legacy_only(self) -> None:
        importlib.reload(computed)
        self.assertEqual(computed.REALM_MOBILE_REMAP_URLS, {"a": "b"})

    @override_settings(REALM_MOBILE_REMAP_URLS={"x": "y"}, REALM_MOBILE_REMAP_URIS={})
    def test_realm_remap_new_only(self) -> None:
        importlib.reload(computed)
        self.assertEqual(computed.REALM_MOBILE_REMAP_URLS, {"x": "y"})

    @override_settings(REALM_MOBILE_REMAP_URLS={"x": "y"}, REALM_MOBILE_REMAP_URIS={"a": "b"})
    def test_realm_remap_precedence(self) -> None:
        importlib.reload(computed)
        self.assertEqual(computed.REALM_MOBILE_REMAP_URLS, {"x": "y"})
