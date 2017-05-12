from __future__ import absolute_import
from __future__ import print_function

from django.test import TestCase

from zerver.middleware import is_slow_query

class SlowQueryTest(TestCase):
    def test_is_slow_query(self):
        # type: () -> None
        self.assertFalse(is_slow_query(1.1, '/some/random/url'))
        self.assertTrue(is_slow_query(2, '/some/random/url'))
        self.assertTrue(is_slow_query(5.1, '/activity'))
        self.assertFalse(is_slow_query(2, '/activity'))
        self.assertFalse(is_slow_query(2, '/json/report_error'))
        self.assertFalse(is_slow_query(2, '/api/v1/deployments/report_error'))
        self.assertFalse(is_slow_query(2, '/realm_activity/whatever'))
        self.assertFalse(is_slow_query(2, '/user_activity/whatever'))
        self.assertFalse(is_slow_query(9, '/accounts/webathena_kerberos_login/'))
        self.assertTrue(is_slow_query(11, '/accounts/webathena_kerberos_login/'))
