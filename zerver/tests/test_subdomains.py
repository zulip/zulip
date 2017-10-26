
import mock
from typing import Any, List

from django.test import TestCase, override_settings

from zerver.lib.subdomains import get_subdomain
from zerver.models import Realm

class SubdomainsTest(TestCase):
    def test_get_subdomain(self):
        # type: () -> None

        def request_mock(host):
            # type: (str) -> Any
            request = mock.Mock(spec=['get_host'])
            request.attach_mock(mock.Mock(return_value=host), 'get_host')
            return request

        def test(expected, host, *, root_aliases=[]):
            # type: (str, str, List[str]) -> None
            with self.settings(EXTERNAL_HOST='example.org',
                               ROOT_SUBDOMAIN_ALIASES=root_aliases):
                self.assertEqual(get_subdomain(request_mock(host)), expected)
                self.assertEqual(get_subdomain(request_mock(host + ':443')), expected)

        ROOT = Realm.SUBDOMAIN_FOR_ROOT_DOMAIN
        test(ROOT, 'example.org')
        test('foo', 'foo.example.org')
        test(ROOT, 'www.example.org', root_aliases=['www'])
        test(ROOT, 'arbitrary.com')
