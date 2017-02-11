# -*- coding: utf-8 -*-
from __future__ import absolute_import

from typing import Any, Dict

from zerver.lib.test_helpers import (
    get_user_profile_by_email,
)

from zerver.lib.test_classes import (
    ZulipTestCase,
)

from zerver.models import (
    UserProfile, UserTutorial
)

import ujson

class TutorialHotspotTests(ZulipTestCase):
    def set_tutorial_state(self, tutorial_object, update_dict):
        # type: (Any, Dict) -> None
        for tutorial_piece, value in update_dict.items():
            setattr(tutorial_object.tutorial_pieces, tutorial_piece, value)
        tutorial_object.save()

    def test_get_next_tutorial_pieces(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        user = get_user_profile_by_email(email)
        self.login(email)
        result = self.client_get('/json/users/me/tutorial')
        self.assert_json_success(result)
        self.assertEquals(['welcome'], ujson.loads(result.content)['next_pieces'])

        tutorial = UserTutorial.objects.get(user_profile=user)
        tutorial_state = {'welcome': True, 'streams': False, 'topics': True, 'narrowing': False, 'replying': False, 'get_started': False}
        self.set_tutorial_state(tutorial, tutorial_state)
        result = self.client_get('/json/users/me/tutorial')
        self.assert_json_success(result)
        self.assertEquals(['streams', 'narrowing'], ujson.loads(result.content)['next_pieces'])

        tutorial_state = {'welcome': True, 'streams': True, 'topics': True, 'narrowing': True, 'replying': False, 'get_started': False}
        self.set_tutorial_state(tutorial, tutorial_state)
        result = self.client_get('/json/users/me/tutorial')
        self.assert_json_success(result)
        self.assertEquals(['replying', 'get_started'], ujson.loads(result.content)['next_pieces'])

    def test_update_tutorial_state(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        user = get_user_profile_by_email(email)
        self.login(email)
        (tutorial, created) = UserTutorial.objects.get_or_create(user_profile=user)
        tutorial_state = {'welcome': True, 'streams': True, 'topics': False, 'narrowing': False, 'replying': False, 'get_started': False}
        self.set_tutorial_state(tutorial, tutorial_state)
        update_state = {'welcome': True, 'streams': True, 'topics': True, 'narrowing': True, 'replying': False, 'get_started': True}
        update_state_json = ujson.dumps(update_state)
        result = self.client_patch('/json/users/me/tutorial', {'update_dict': update_state_json})
        self.assert_json_success(result)
        self.assertEquals(['replying'], ujson.loads(result.content)['next_pieces'])
        updated_tutorial = UserTutorial.objects.get(user_profile=user)
        for flag in update_state:
            self.assertEquals(getattr(updated_tutorial.tutorial_pieces, flag).is_set, update_state[flag])

    def test_restart_tutorial(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        user = get_user_profile_by_email(email)
        self.login(email)
        (tutorial, created) = UserTutorial.objects.get_or_create(user_profile=user)
        tutorial_state = {'welcome': True, 'streams': True, 'topics': True, 'narrowing': False, 'replying': False, 'get_started': False}
        self.set_tutorial_state(tutorial, tutorial_state)
        updated_tutorial = UserTutorial.objects.get(user_profile=user)
        for flag in tutorial_state:
            self.assertEquals(getattr(updated_tutorial.tutorial_pieces, flag).is_set, tutorial_state[flag])
        result = self.client_post('/json/users/me/tutorial')
        self.assert_json_success(result)
        restarted_tutorial = UserTutorial.objects.get(user_profile=user)
        for flag in tutorial_state:
            self.assertEquals(getattr(restarted_tutorial.tutorial_pieces, flag).is_set, False)
