# -*- coding: utf-8 -*-

import re

from zerver.lib.actions import get_realm, do_add_realm_filter
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import RealmFilter

class RealmFilterTest(ZulipTestCase):

    def test_list(self) -> None:
        email = self.example_email('iago')
        self.login(email)
        realm = get_realm('zulip')
        do_add_realm_filter(
            realm,
            "#(?P<id>[123])",
            "https://realm.com/my_realm_filter/%(id)s")
        result = self.client_get("/json/realm/filters")
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)
        self.assertEqual(len(result.json()["filters"]), 1)

    def test_create(self) -> None:
        email = self.example_email('iago')
        self.login(email)
        data = {"pattern": "", "url_format_string": "https://realm.com/my_realm_filter/%(id)s"}
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(result, 'This field cannot be blank.')

        data['pattern'] = '$a'
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(result, 'Invalid filter pattern.  Valid characters are [ a-zA-Z_#=/:+!-].')

        data['pattern'] = r'ZUL-(?P<id>\d++)'
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(result, 'Invalid filter pattern.  Valid characters are [ a-zA-Z_#=/:+!-].')

        data['pattern'] = r'ZUL-(?P<id>\d+)'
        data['url_format_string'] = '$fgfg'
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(result, 'Enter a valid URL.')

        data['pattern'] = r'ZUL-(?P<id>\d+)'
        data['url_format_string'] = 'https://realm.com/my_realm_filter/'
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(result, 'Invalid URL format string.')

        data['url_format_string'] = 'https://realm.com/my_realm_filter/#hashtag/%(id)s'
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data['pattern'], 'ZUL-15'))

        data['pattern'] = r'ZUL2-(?P<id>\d+)'
        data['url_format_string'] = 'https://realm.com/my_realm_filter/?value=%(id)s'
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data['pattern'], 'ZUL2-15'))

        data['pattern'] = r'_code=(?P<id>[0-9a-zA-Z]+)'
        data['url_format_string'] = 'https://realm.com/my_realm_filter/?value=%(id)s'
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data['pattern'], '_code=123abcdZ'))

        data['pattern'] = r'PR (?P<id>[0-9]+)'
        data['url_format_string'] = 'https://realm.com/my_realm_filter/?value=%(id)s'
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data['pattern'], 'PR 123'))

        data['pattern'] = r'lp/(?P<id>[0-9]+)'
        data['url_format_string'] = 'https://realm.com/my_realm_filter/?value=%(id)s'
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data['pattern'], 'lp/123'))

        data['pattern'] = r'lp:(?P<id>[0-9]+)'
        data['url_format_string'] = 'https://realm.com/my_realm_filter/?value=%(id)s'
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data['pattern'], 'lp:123'))

        data['pattern'] = r'!(?P<id>[0-9]+)'
        data['url_format_string'] = 'https://realm.com/my_realm_filter/?value=%(id)s'
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data['pattern'], '!123'))

        # This is something we'd like to support, but don't currently;
        # this test is a reminder of something we should allow in the
        # future.
        data['pattern'] = r'(?P<org>[a-zA-Z0-9_-]+)/(?P<repo>[a-zA-Z0-9_-]+)#(?P<id>[0-9]+)'
        data['url_format_string'] = 'https://github.com/%(org)s/%(repo)s/issue/%(id)s'
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)
        self.assertIsNotNone(re.match(data['pattern'], 'zulip/zulip#123'))

    def test_not_realm_admin(self) -> None:
        email = self.example_email('hamlet')
        self.login(email)
        result = self.client_post("/json/realm/filters")
        self.assert_json_error(result, 'Must be an organization administrator')
        result = self.client_delete("/json/realm/filters/15")
        self.assert_json_error(result, 'Must be an organization administrator')

    def test_delete(self) -> None:
        email = self.example_email('iago')
        self.login(email)
        realm = get_realm('zulip')
        filter_id = do_add_realm_filter(
            realm,
            "#(?P<id>[123])",
            "https://realm.com/my_realm_filter/%(id)s")
        filters_count = RealmFilter.objects.count()
        result = self.client_delete("/json/realm/filters/{0}".format(filter_id + 1))
        self.assert_json_error(result, 'Filter not found')

        result = self.client_delete("/json/realm/filters/{0}".format(filter_id))
        self.assert_json_success(result)
        self.assertEqual(RealmFilter.objects.count(), filters_count - 1)
