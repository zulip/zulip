# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

from zerver.lib.test_classes import (
    ZulipTestCase,
)

from zerver.models import (
    get_user_profile_by_email, BuddyList
)

from zerver.lib.events import (
    get_buddy_list
)

import ujson

class BuddyListUpdateTest(ZulipTestCase):
    def test_update_buddy_list(self):
        # type: () -> None
        user_email = "hamlet@zulip.com"
        buddy_email = "iago@zulip.com"

        self.login(user_email)
        user_profile = get_user_profile_by_email(user_email)
        buddy_profile = get_user_profile_by_email(buddy_email)

        result = self.client_patch("/json/users/me/buddy", {
            'buddy_id': ujson.dumps(-1),
            'should_add': ujson.dumps(True),
        })
        self.assert_json_error(result, "No such user with user id -1")

        result = self.client_patch("/json/users/me/buddy", {
            'buddy_id': ujson.dumps(buddy_profile.id),
            'should_add': ujson.dumps(True),
        })
        self.assert_json_success(result)
        self.assertEqual(get_buddy_list(user_profile), {buddy_profile.id})

        result = self.client_patch("/json/users/me/buddy", {
            'buddy_id': ujson.dumps(buddy_profile.id),
            'should_add': ujson.dumps(False),
        })
        self.assert_json_success(result)
        self.assertNotEqual(get_buddy_list(user_profile), {buddy_profile.id})

        result = self.client_patch("/json/users/me/buddy", {
            'buddy_id': ujson.dumps(user_profile.id),
            'should_add': ujson.dumps(True),
        })
        self.assert_json_error(result, "User and buddy user are same")

        community_buddy_user_profile = get_user_profile_by_email("bob@foo.edu")
        result = self.client_patch("/json/users/me/buddy", {
            'buddy_id': ujson.dumps(community_buddy_user_profile.id),
            'should_add': ujson.dumps(True),
        })
        self.assert_json_error(result, "User and buddy user belong to different realms")
