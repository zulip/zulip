# -*- coding: utf-8 -*-
from typing import Any, List, Optional, Text

import ujson
import django
import mock

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_groups import (
    check_add_user_to_user_group,
    check_remove_user_from_user_group,
    create_user_group,
    get_user_groups,
    user_groups_in_realm,
)
from zerver.models import UserProfile, UserGroup, get_realm, Realm

class UserGroupTestCase(ZulipTestCase):
    def create_user_group_for_test(self, group_name,
                                   realm=get_realm('zulip')):
        # type: (Text, Realm) -> UserGroup
        members = [self.example_user('othello')]
        return create_user_group(group_name, members, realm)

    def test_user_groups_in_realm(self):
        # type: () -> None
        realm = get_realm('zulip')
        self.assertEqual(len(user_groups_in_realm(realm)), 0)
        self.create_user_group_for_test('support')
        user_groups = user_groups_in_realm(realm)
        self.assertEqual(len(user_groups), 1)
        self.assertEqual(user_groups[0].name, 'support')

    def test_get_user_groups(self):
        # type: () -> None
        othello = self.example_user('othello')
        self.create_user_group_for_test('support')
        user_groups = get_user_groups(othello)
        self.assertEqual(len(user_groups), 1)
        self.assertEqual(user_groups[0].name, 'support')

    def test_check_add_user_to_user_group(self):
        # type: () -> None
        user_group = self.create_user_group_for_test('support')
        hamlet = self.example_user('hamlet')
        self.assertTrue(check_add_user_to_user_group(hamlet, user_group))
        self.assertFalse(check_add_user_to_user_group(hamlet, user_group))

    def test_check_remove_user_from_user_group(self):
        # type: () -> None
        user_group = self.create_user_group_for_test('support')
        othello = self.example_user('othello')
        self.assertTrue(check_remove_user_from_user_group(othello, user_group))
        self.assertFalse(check_remove_user_from_user_group(othello, user_group))

        with mock.patch('zerver.lib.user_groups.remove_user_from_user_group',
                        side_effect=Exception):
            self.assertFalse(check_remove_user_from_user_group(othello, user_group))

class UserGroupAPITestCase(ZulipTestCase):
    def test_user_group_create(self):
        # type: () -> None
        hamlet = self.example_user('hamlet')

        # Test success
        self.login(self.example_email("hamlet"))
        params = {
            'name': 'support',
            'members': ujson.dumps([hamlet.id]),
            'description': 'Support team',
        }
        result = self.client_post('/json/user_groups/create', info=params)
        self.assert_json_success(result)
        self.assert_length(UserGroup.objects.all(), 1)

        # Test invalid member error
        params = {
            'name': 'backend',
            'members': ujson.dumps([1111]),
            'description': 'Backend team',
        }
        result = self.client_post('/json/user_groups/create', info=params)
        self.assert_json_error(result, "Invalid user ID: 1111")
        self.assert_length(UserGroup.objects.all(), 1)

        # Test we cannot add hamlet again
        params = {
            'name': 'support',
            'members': ujson.dumps([hamlet.id]),
            'description': 'Support team',
        }
        result = self.client_post('/json/user_groups/create', info=params)
        self.assert_json_error(result, "User group 'support' already exists.")
        self.assert_length(UserGroup.objects.all(), 1)

    def test_user_group_update(self):
        # type: () -> None
        hamlet = self.example_user('hamlet')
        self.login(self.example_email("hamlet"))
        params = {
            'name': 'support',
            'members': ujson.dumps([hamlet.id]),
            'description': 'Support team',
        }
        self.client_post('/json/user_groups/create', info=params)
        user_group = UserGroup.objects.first()

        # Test success
        params = {
            'name': 'help',
            'description': 'Troubleshooting team',
        }
        result = self.client_patch('/json/user_groups/{}'.format(user_group.id), info=params)
        self.assert_json_success(result)
        self.assertEqual(result.json()['name'], 'Name successfully updated.')
        self.assertEqual(result.json()['description'], 'Description successfully updated.')

        # Test when new data is not supplied.
        result = self.client_patch('/json/user_groups/{}'.format(user_group.id), info={})
        self.assert_json_error(result, "No new data supplied")

        # Test when invalid user group is supplied
        params = {'name': 'help'}
        result = self.client_patch('/json/user_groups/1111', info=params)
        self.assert_json_error(result, "Invalid user group")
