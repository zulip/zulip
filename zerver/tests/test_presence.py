# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

from django.http import HttpResponse
from django.utils import timezone

from typing import Any, Dict
from zerver.lib.test_helpers import (
    get_user_profile_by_email,
    make_client,
    queries_captured,
)
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.models import (
    email_to_domain,
    Client,
    UserActivity,
    UserProfile,
)

import datetime
import ujson

class ActivityTest(ZulipTestCase):
    def test_activity(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        client, _ = Client.objects.get_or_create(name='website')
        query = '/json/users/me/pointer'
        last_visit = timezone.now()
        count = 150
        for user_profile in UserProfile.objects.all():
            UserActivity.objects.get_or_create(
                user_profile=user_profile,
                client=client,
                query=query,
                count=count,
                last_visit=last_visit
            )
        with queries_captured() as queries:
            self.client_get('/activity')

        self.assert_max_length(queries, 13)

class UserPresenceTests(ZulipTestCase):
    def test_invalid_presence(self):
        # type: () -> None
        email = "hamlet@zulip.com"
        self.login(email)
        result = self.client_post("/json/users/me/presence", {'status': 'foo'})
        self.assert_json_error(result, 'Invalid presence status: foo')

    def test_set_idle(self):
        # type: () -> None
        email = "hamlet@zulip.com"
        self.login(email)
        client = 'website'

        result = self.client_post("/json/users/me/presence", {'status': 'idle'})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'idle')
        self.assertIn('timestamp', json['presences'][email][client])
        self.assertIsInstance(json['presences'][email][client]['timestamp'], int)
        self.assertEqual(list(json['presences'].keys()), ['hamlet@zulip.com'])
        timestamp = json['presences'][email][client]['timestamp']

        email = "othello@zulip.com"
        self.login(email)
        result = self.client_post("/json/users/me/presence", {'status': 'idle'})
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'idle')
        self.assertEqual(json['presences']['hamlet@zulip.com'][client]['status'], 'idle')
        self.assertEqual(sorted(json['presences'].keys()), ['hamlet@zulip.com', 'othello@zulip.com'])
        newer_timestamp = json['presences'][email][client]['timestamp']
        self.assertGreaterEqual(newer_timestamp, timestamp)

    def test_set_active(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        client = 'website'

        result = self.client_post("/json/users/me/presence", {'status': 'idle'})

        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences']["hamlet@zulip.com"][client]['status'], 'idle')

        email = "othello@zulip.com"
        self.login("othello@zulip.com")
        result = self.client_post("/json/users/me/presence", {'status': 'idle'})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'idle')
        self.assertEqual(json['presences']['hamlet@zulip.com'][client]['status'], 'idle')

        result = self.client_post("/json/users/me/presence", {'status': 'active'})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'active')
        self.assertEqual(json['presences']['hamlet@zulip.com'][client]['status'], 'idle')

    def test_no_mit(self):
        # type: () -> None
        """Zephyr mirror realms such as MIT never get a list of users"""
        self.login("espuser@mit.edu")
        result = self.client_post("/json/users/me/presence", {'status': 'idle'})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'], {})

    def test_mirror_presence(self):
        # type: () -> None
        """Zephyr mirror realms find out the status of their mirror bot"""
        email = 'espuser@mit.edu'
        user_profile = get_user_profile_by_email(email)
        self.login(email)

        def post_presence():
            # type: () -> Dict[str, Any]
            result = self.client_post("/json/users/me/presence", {'status': 'idle'})
            self.assert_json_success(result)
            json = ujson.loads(result.content)
            return json

        json = post_presence()
        self.assertEqual(json['zephyr_mirror_active'], False)

        self._simulate_mirror_activity_for_user(user_profile)
        json = post_presence()
        self.assertEqual(json['zephyr_mirror_active'], True)

    def _simulate_mirror_activity_for_user(self, user_profile):
        # type: (UserProfile) -> None
        last_visit = timezone.now()
        client = make_client('zephyr_mirror')

        UserActivity.objects.get_or_create(
            user_profile=user_profile,
            client=client,
            query='get_events_backend',
            count=2,
            last_visit=last_visit
        )

    def test_same_realm(self):
        # type: () -> None
        self.login("espuser@mit.edu")
        self.client_post("/json/users/me/presence", {'status': 'idle'})
        result = self.client_post("/accounts/logout/")

        # Ensure we don't see hamlet@zulip.com information leakage
        self.login("hamlet@zulip.com")
        result = self.client_post("/json/users/me/presence", {'status': 'idle'})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences']["hamlet@zulip.com"]["website"]['status'], 'idle')
        # We only want @zulip.com emails
        for email in json['presences'].keys():
            self.assertEqual(email_to_domain(email), 'zulip.com')
