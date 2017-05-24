# -*- coding: utf-8 -*-
from __future__ import absolute_import

from zerver.lib.actions import get_realm, do_add_realm_filter
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import RealmFilter
import ujson


class RealmFilterTest(ZulipTestCase):

    def test_list(self):
        # type: () -> None
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
        content = ujson.loads(result.content)
        self.assertEqual(len(content["filters"]), 1)

    def test_create(self):
        # type: () -> None
        email = self.example_email('iago')
        self.login(email)
        data = {"pattern": "", "url_format_string": "https://realm.com/my_realm_filter/%(id)s"}
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(result, 'This field cannot be blank.')

        data['pattern'] = '$a'
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(result, 'Invalid filter pattern, you must use the following format OPTIONAL_PREFIX(?P<id>.+)')

        data['pattern'] = 'ZUL-(?P<id>\d++)'
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(result, 'Invalid filter pattern, you must use the following format OPTIONAL_PREFIX(?P<id>.+)')

        data['pattern'] = 'ZUL-(?P<id>\d+)'
        data['url_format_string'] = '$fgfg'
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_error(result, 'URL format string must be in the following format: `https://example.com/%(\\w+)s`')

        data['url_format_string'] = 'https://realm.com/my_realm_filter/%(id)s'
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)

        data['pattern'] = 'ZUL2-(?P<id>\d+)'
        data['url_format_string'] = 'https://realm.com/my_realm_filter/?value=%(id)s'
        result = self.client_post("/json/realm/filters", info=data)
        self.assert_json_success(result)

    def test_not_realm_admin(self):
        # type: () -> None
        email = self.example_email('hamlet')
        self.login(email)
        result = self.client_post("/json/realm/filters")
        self.assert_json_error(result, 'Must be a realm administrator')
        result = self.client_delete("/json/realm/filters/15")
        self.assert_json_error(result, 'Must be a realm administrator')

    def test_delete(self):
        # type: () -> None
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
