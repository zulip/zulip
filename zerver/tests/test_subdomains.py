
import mock
from typing import Any, Dict, List

from django.test import TestCase

from zerver.lib.subdomains import get_subdomain
from zerver.models import Realm

class SubdomainsTest(TestCase):
    def test_get_subdomain(self) -> None:

        def request_mock(host: str) -> Any:
            request = mock.Mock(spec=['get_host'])
            request.attach_mock(mock.Mock(return_value=host), 'get_host')
            return request

        def test(expected: str, host: str, *, plusport: bool=True,
                 external_host: str='example.org',
                 realm_hosts: Dict[str, str]={},
                 root_aliases: List[str]=[]) -> None:
            with self.settings(EXTERNAL_HOST=external_host,
                               REALM_HOSTS=realm_hosts,
                               ROOT_SUBDOMAIN_ALIASES=root_aliases):
                self.assertEqual(get_subdomain(request_mock(host)), expected)
                if plusport and ':' not in host:
                    self.assertEqual(get_subdomain(request_mock(host + ':443')),
                                     expected)

        ROOT = Realm.SUBDOMAIN_FOR_ROOT_DOMAIN

        # Basics
        test(ROOT, 'example.org')
        test('foo', 'foo.example.org')
        test(ROOT, 'www.example.org', root_aliases=['www'])

        # Unrecognized patterns fall back to root
        test(ROOT, 'arbitrary.com')
        test(ROOT, 'foo.example.org.evil.com')

        # REALM_HOSTS adds a name,
        test('bar', 'chat.barbar.com', realm_hosts={'bar': 'chat.barbar.com'})
        # ... exactly, ...
        test(ROOT, 'surchat.barbar.com', realm_hosts={'bar': 'chat.barbar.com'})
        test(ROOT, 'foo.chat.barbar.com', realm_hosts={'bar': 'chat.barbar.com'})
        # ... and leaves the subdomain in place too.
        test('bar', 'bar.example.org', realm_hosts={'bar': 'chat.barbar.com'})

        # Any port is fine in Host if there's none in EXTERNAL_HOST, ...
        test('foo', 'foo.example.org:443', external_host='example.org')
        test('foo', 'foo.example.org:12345', external_host='example.org')
        # ... but an explicit port in EXTERNAL_HOST must be explicitly matched in Host.
        test(ROOT, 'foo.example.org', external_host='example.org:12345')
        test(ROOT, 'foo.example.org', external_host='example.org:443', plusport=False)
        test('foo', 'foo.example.org:443', external_host='example.org:443')
