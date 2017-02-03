# -*- coding: utf-8 -*-
from __future__ import absolute_import

from zerver.lib.actions import do_change_is_admin, do_create_realm
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_realm, get_realm_by_email_domain, \
    get_user_profile_by_email, GetRealmByDomainException, RealmAlias
import ujson


class RealmAliasTest(ZulipTestCase):

    def test_list(self):
        # type: () -> None
        self.login("iago@zulip.com")
        realm = get_realm('zulip')
        alias = RealmAlias(realm=realm, domain='zulip.org')
        alias.save()
        result = self.client_get("/json/realm/domains")
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)
        content = ujson.loads(result.content)
        self.assertEqual(len(content['domains']), 2)

    def test_not_realm_admin(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        result = self.client_post("/json/realm/domains")
        self.assert_json_error(result, 'Must be a realm administrator')
        result = self.client_delete("/json/realm/domains/15")
        self.assert_json_error(result, 'Must be a realm administrator')

    def test_create(self):
        # type: () -> None
        self.login("iago@zulip.com")
        data = {'domain': ujson.dumps('')}
        result = self.client_post("/json/realm/domains", info=data)
        self.assert_json_error(result, 'Invalid domain: Domain can\'t be empty.')

        data = {'domain': ujson.dumps('zulip.org')}
        result = self.client_post("/json/realm/domains", info=data)
        self.assert_json_success(result)

        result = self.client_post("/json/realm/domains", info=data)
        self.assert_json_error(result, 'The domain zulip.org is already a part of your organization.')

        self.login("sipbtest@mit.edu")
        mit_user_profile = get_user_profile_by_email("sipbtest@mit.edu")
        do_change_is_admin(mit_user_profile, True)
        result = self.client_post("/json/realm/domains", info=data)
        self.assert_json_error(result, 'The domain zulip.org belongs to another organization.')
        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            result = self.client_post("/json/realm/domains", info=data,
                                      HTTP_HOST=mit_user_profile.realm.host)
            self.assert_json_success(result)

    def test_delete(self):
        # type: () -> None
        self.login("iago@zulip.com")
        realm = get_realm('zulip')
        RealmAlias.objects.create(realm=realm, domain='zulip.org')
        aliases_count = RealmAlias.objects.count()
        result = self.client_delete("/json/realm/domains/non-existent.com")
        self.assertEqual(result.status_code, 400)
        self.assert_json_error(result, 'No entry found for domain non-existent.com.')

        result = self.client_delete("/json/realm/domains/zulip.org")
        self.assert_json_success(result)
        self.assertEqual(RealmAlias.objects.count(), aliases_count - 1)

    def test_get_realm_by_email_domain(self):
        # type: () -> None
        self.assertEqual(get_realm_by_email_domain('user@zulip.com').string_id, 'zulip')
        self.assertEqual(get_realm_by_email_domain('user@fakedomain.com'), None)
        with self.settings(REALMS_HAVE_SUBDOMAINS = True), (
                self.assertRaises(GetRealmByDomainException)):
            get_realm_by_email_domain('user@zulip.com')
