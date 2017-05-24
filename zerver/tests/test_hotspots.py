# -*- coding: utf-8 -*-
from __future__ import absolute_import

from zerver.lib.actions import do_mark_hotspot_as_read
from zerver.lib.hotspots import ALL_HOTSPOTS, get_next_hotspots
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile, UserHotspot
from zerver.views.hotspots import mark_hotspot_as_read

from typing import Any, Dict
import ujson

# Splitting this out, since I imagine this will eventually have most of the
# complicated hotspots logic.
class TestGetNextHotspots(ZulipTestCase):
    def test_first_hotspot(self):
        # type: () -> None
        user = self.example_user('hamlet')
        self.assertEqual(get_next_hotspots(user), ['welcome'])

    def test_some_done_some_not(self):
        # type: () -> None
        user = self.example_user('hamlet')
        do_mark_hotspot_as_read(user, 'welcome')
        do_mark_hotspot_as_read(user, 'topics')
        self.assertEqual(get_next_hotspots(user), ['streams'])

    def test_all_done(self):
        # type: () -> None
        user = self.example_user('hamlet')
        for hotspot in ALL_HOTSPOTS:
            do_mark_hotspot_as_read(user, hotspot)
        self.assertEqual(get_next_hotspots(user), [])

class TestHotspots(ZulipTestCase):
    def test_do_mark_hotspot_as_read(self):
        # type: () -> None
        user = self.example_user('hamlet')
        do_mark_hotspot_as_read(user, 'streams')
        self.assertEqual(list(UserHotspot.objects.filter(user=user)
                              .values_list('hotspot', flat=True)), ['streams'])

    def test_hotspots_url_endpoint(self):
        # type: () -> None
        user = self.example_user('hamlet')
        self.login(user.email)
        result = self.client_post('/json/users/me/hotspots',
                                  {'hotspot': ujson.dumps('welcome')})
        self.assert_json_success(result)
        self.assertEqual(list(UserHotspot.objects.filter(user=user)
                              .values_list('hotspot', flat=True)), ['welcome'])

        result = self.client_post('/json/users/me/hotspots',
                                  {'hotspot': ujson.dumps('invalid')})
        self.assert_json_error(result, "Unknown hotspot: invalid")
        self.assertEqual(list(UserHotspot.objects.filter(user=user)
                              .values_list('hotspot', flat=True)), ['welcome'])
