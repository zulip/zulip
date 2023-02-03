from typing import Any, Mapping, Sequence
from unittest import mock

from django.conf import settings

import zerver.lib.upload
from zerver.lib.subdomains import get_subdomain, is_static_or_current_realm_url
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import create_s3_buckets, use_s3_backend
from zerver.models import Realm


class SubdomainsTest(ZulipTestCase):
    def test_get_subdomain(self) -> None:
        def request_mock(host: str) -> Any:
            request = mock.Mock(spec=["get_host"])
            request.attach_mock(mock.Mock(return_value=host), "get_host")
            return request

        def test(
            expected: str,
            host: str,
            *,
            plusport: bool = True,
            external_host: str = "example.org",
            realm_hosts: Mapping[str, str] = {},
            root_aliases: Sequence[str] = [],
        ) -> None:
            with self.settings(
                EXTERNAL_HOST=external_host,
                REALM_HOSTS=realm_hosts,
                ROOT_SUBDOMAIN_ALIASES=root_aliases,
            ):
                self.assertEqual(get_subdomain(request_mock(host)), expected)
                if plusport and ":" not in host:
                    self.assertEqual(get_subdomain(request_mock(host + ":443")), expected)

        ROOT = Realm.SUBDOMAIN_FOR_ROOT_DOMAIN

        # Basics
        test(ROOT, "example.org")
        test("foo", "foo.example.org")
        test(ROOT, "www.example.org", root_aliases=["www"])

        # Unrecognized patterns fall back to root
        test(ROOT, "arbitrary.com")
        test(ROOT, "foo.example.org.evil.com")

        # REALM_HOSTS adds a name,
        test("bar", "chat.barbar.com", realm_hosts={"bar": "chat.barbar.com"})
        # ... exactly, ...
        test(ROOT, "surchat.barbar.com", realm_hosts={"bar": "chat.barbar.com"})
        test(ROOT, "foo.chat.barbar.com", realm_hosts={"bar": "chat.barbar.com"})
        # ... and leaves the subdomain in place too.
        test("bar", "bar.example.org", realm_hosts={"bar": "chat.barbar.com"})

        # Any port is fine in Host if there's none in EXTERNAL_HOST, ...
        test("foo", "foo.example.org:443", external_host="example.org")
        test("foo", "foo.example.org:12345", external_host="example.org")
        # ... but an explicit port in EXTERNAL_HOST must be explicitly matched in Host.
        test(ROOT, "foo.example.org", external_host="example.org:12345")
        test(ROOT, "foo.example.org", external_host="example.org:443", plusport=False)
        test("foo", "foo.example.org:443", external_host="example.org:443")

    def test_is_static_or_current_realm_url(self) -> None:
        realm = self.example_user("hamlet").realm

        def test(url: str) -> bool:
            return is_static_or_current_realm_url(url, realm)

        self.assertTrue(test("/static/images/logo/zulip-org-logo.svg"))
        self.assertTrue(test("/anything"))
        self.assertFalse(test("https://zulip.com"))
        self.assertFalse(test("http://zulip.com"))
        self.assertTrue(test(f"{realm.uri}"))

        self.assertFalse(test(f"{realm.uri}@www.google.com"))

        # We don't have an existing configuration STATIC_URL with this
        # format, but it's worth testing in case that changes.
        with self.settings(STATIC_URL="https://zulipstatic.example.com"):
            evil_url = f"{settings.STATIC_URL}@evil.example.com"
            self.assertEqual(evil_url, "https://zulipstatic.example.com@evil.example.com")
            self.assertTrue(test(f"{settings.STATIC_URL}/x"))
            self.assertFalse(test(evil_url))
            self.assertFalse(test(f"{evil_url}/x"))
            self.assertTrue(test(f"{realm.uri}"))
            self.assertTrue(test("/static/images/logo/zulip-org-logo.svg"))
            self.assertTrue(test("/anything"))

    @use_s3_backend
    def test_is_static_or_current_realm_url_with_s3(self) -> None:
        create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]

        realm = self.example_user("hamlet").realm

        def test(url: str) -> bool:
            return is_static_or_current_realm_url(url, realm)

        upload_backend = zerver.lib.upload.upload_backend
        self.assertTrue(test(upload_backend.get_realm_icon_url(realm.id, version=1)))
        self.assertTrue(test(upload_backend.get_realm_logo_url(realm.id, version=1, night=False)))
        self.assertTrue(test(upload_backend.get_avatar_url("deadbeefcafe")))
        self.assertTrue(test(upload_backend.get_emoji_url("emoji.gif", realm.id)))
