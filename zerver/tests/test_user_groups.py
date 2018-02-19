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
    get_memberships_of_users,
    user_groups_in_realm_serialized,
)
from zerver.models import UserProfile, UserGroup, get_realm, Realm, \
    UserGroupMembership

class UserGroupTestCase(ZulipTestCase):
    def create_user_group_for_test(self, group_name: Text,
                                   realm: Realm=get_realm('zulip')) -> UserGroup:
        members = [self.example_user('othello')]
        return create_user_group(group_name, members, realm)

    def test_user_groups_in_realm(self) -> None:
        realm = get_realm('zulip')
        self.assertEqual(len(user_groups_in_realm(realm)), 1)
        self.create_user_group_for_test('support')
        user_groups = user_groups_in_realm(realm)
        self.assertEqual(len(user_groups), 2)
        names = set([ug.name for ug in user_groups])
        self.assertEqual(names, set(['hamletcharacters', 'support']))

    def test_user_groups_in_realm_serialized(self) -> None:
        realm = get_realm('zulip')
        user_group = UserGroup.objects.first()
        membership = UserGroupMembership.objects.filter(user_group=user_group)
        membership = membership.values_list('user_profile_id', flat=True)
        empty_user_group = create_user_group('newgroup', [], realm)

        user_groups = user_groups_in_realm_serialized(realm)
        self.assertEqual(len(user_groups), 2)
        self.assertEqual(user_groups[0]['id'], user_group.id)
        self.assertEqual(user_groups[0]['name'], 'hamletcharacters')
        self.assertEqual(user_groups[0]['description'], 'Characters of Hamlet')
        self.assertEqual(set(user_groups[0]['members']), set(membership))

        self.assertEqual(user_groups[1]['id'], empty_user_group.id)
        self.assertEqual(user_groups[1]['name'], 'newgroup')
        self.assertEqual(user_groups[1]['description'], '')
        self.assertEqual(user_groups[1]['members'], [])

    def test_get_user_groups(self) -> None:
        othello = self.example_user('othello')
        self.create_user_group_for_test('support')
        user_groups = get_user_groups(othello)
        self.assertEqual(len(user_groups), 1)
        self.assertEqual(user_groups[0].name, 'support')

    def test_check_add_user_to_user_group(self) -> None:
        user_group = self.create_user_group_for_test('support')
        hamlet = self.example_user('hamlet')
        self.assertTrue(check_add_user_to_user_group(hamlet, user_group))
        self.assertFalse(check_add_user_to_user_group(hamlet, user_group))

    def test_check_remove_user_from_user_group(self) -> None:
        user_group = self.create_user_group_for_test('support')
        othello = self.example_user('othello')
        self.assertTrue(check_remove_user_from_user_group(othello, user_group))
        self.assertFalse(check_remove_user_from_user_group(othello, user_group))

        with mock.patch('zerver.lib.user_groups.remove_user_from_user_group',
                        side_effect=Exception):
            self.assertFalse(check_remove_user_from_user_group(othello, user_group))

class UserGroupAPITestCase(ZulipTestCase):
    def test_user_group_create(self) -> None:
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
        self.assert_length(UserGroup.objects.all(), 2)

        # Test invalid member error
        params = {
            'name': 'backend',
            'members': ujson.dumps([1111]),
            'description': 'Backend team',
        }
        result = self.client_post('/json/user_groups/create', info=params)
        self.assert_json_error(result, "Invalid user ID: 1111")
        self.assert_length(UserGroup.objects.all(), 2)

        # Test we cannot add hamlet again
        params = {
            'name': 'support',
            'members': ujson.dumps([hamlet.id]),
            'description': 'Support team',
        }
        result = self.client_post('/json/user_groups/create', info=params)
        self.assert_json_error(result, "User group 'support' already exists.")
        self.assert_length(UserGroup.objects.all(), 2)

    def test_user_group_update(self) -> None:
        hamlet = self.example_user('hamlet')
        self.login(self.example_email("hamlet"))
        params = {
            'name': 'support',
            'members': ujson.dumps([hamlet.id]),
            'description': 'Support team',
        }
        self.client_post('/json/user_groups/create', info=params)
        user_group = UserGroup.objects.get(name='support')
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

        self.logout()
        # Test when user not a member of user group tries to modify it
        cordelia = self.example_user('cordelia')
        self.login(cordelia.email)
        params = {
            'name': 'help',
            'description': 'Troubleshooting',
        }
        result = self.client_patch('/json/user_groups/{}'.format(user_group.id), info=params)
        self.assert_json_error(result, "Only group members and organization administrators can administer this group.")

        self.logout()
        # Test when organization admin tries to modify group
        iago = self.example_user('iago')
        self.login(iago.email)
        params = {
            'name': 'help',
            'description': 'Troubleshooting',
        }
        result = self.client_patch('/json/user_groups/{}'.format(user_group.id), info=params)
        self.assert_json_success(result)
        self.assertEqual(result.json()['description'], 'Description successfully updated.')

    def test_user_group_delete(self) -> None:
        hamlet = self.example_user('hamlet')
        self.login(self.example_email("hamlet"))
        params = {
            'name': 'support',
            'members': ujson.dumps([hamlet.id]),
            'description': 'Support team',
        }
        self.client_post('/json/user_groups/create', info=params)
        user_group = UserGroup.objects.get(name='support')
        # Test success
        self.assertEqual(UserGroup.objects.count(), 2)
        self.assertEqual(UserGroupMembership.objects.count(), 3)
        result = self.client_delete('/json/user_groups/{}'.format(user_group.id))
        self.assert_json_success(result)
        self.assertEqual(UserGroup.objects.count(), 1)
        self.assertEqual(UserGroupMembership.objects.count(), 2)

        # Test when invalid user group is supplied
        result = self.client_delete('/json/user_groups/1111')
        self.assert_json_error(result, "Invalid user group")

        # Test when user not a member of user group tries to delete it
        params = {
            'name': 'Development',
            'members': ujson.dumps([hamlet.id]),
            'description': 'Development team',
        }
        self.client_post('/json/user_groups/create', info=params)
        user_group = UserGroup.objects.get(name='Development')
        self.assertEqual(UserGroup.objects.count(), 2)
        self.logout()
        cordelia = self.example_user('cordelia')
        self.login(cordelia.email)

        result = self.client_delete('/json/user_groups/{}'.format(user_group.id))
        self.assert_json_error(result, "Only group members and organization administrators can administer this group.")
        self.assertEqual(UserGroup.objects.count(), 2)

        self.logout()
        # Test when organization admin tries to delete group
        iago = self.example_user('iago')
        self.login(iago.email)

        result = self.client_delete('/json/user_groups/{}'.format(user_group.id))
        self.assert_json_success(result)
        self.assertEqual(UserGroup.objects.count(), 1)
        self.assertEqual(UserGroupMembership.objects.count(), 2)

    def test_update_members_of_user_group(self) -> None:
        hamlet = self.example_user('hamlet')
        self.login(self.example_email("hamlet"))
        params = {
            'name': 'support',
            'members': ujson.dumps([hamlet.id]),
            'description': 'Support team',
        }
        self.client_post('/json/user_groups/create', info=params)
        user_group = UserGroup.objects.get(name='support')
        # Test add members
        self.assertEqual(UserGroupMembership.objects.count(), 3)

        othello = self.example_user('othello')
        add = [othello.id]
        params = {'add': ujson.dumps(add)}
        result = self.client_post('/json/user_groups/{}/members'.format(user_group.id),
                                  info=params)
        self.assert_json_success(result)
        self.assertEqual(UserGroupMembership.objects.count(), 4)
        members = get_memberships_of_users(user_group, [hamlet, othello])
        self.assertEqual(len(members), 2)

        # Test adding a member already there.
        result = self.client_post('/json/user_groups/{}/members'.format(user_group.id),
                                  info=params)
        self.assert_json_error(result, "User 6 is already a member of this group")
        self.assertEqual(UserGroupMembership.objects.count(), 4)
        members = get_memberships_of_users(user_group, [hamlet, othello])
        self.assertEqual(len(members), 2)

        self.logout()
        # Test when user not a member of user group tries to add members to it
        cordelia = self.example_user('cordelia')
        self.login(cordelia.email)
        add = [cordelia.id]
        params = {'add': ujson.dumps(add)}
        result = self.client_post('/json/user_groups/{}/members'.format(user_group.id),
                                  info=params)
        self.assert_json_error(result, "Only group members and organization administrators can administer this group.")
        self.assertEqual(UserGroupMembership.objects.count(), 4)

        self.logout()
        # Test when organization admin tries to add members to group
        iago = self.example_user('iago')
        self.login(iago.email)
        aaron = self.example_user('aaron')
        add = [aaron.id]
        params = {'add': ujson.dumps(add)}
        result = self.client_post('/json/user_groups/{}/members'.format(user_group.id),
                                  info=params)
        self.assert_json_success(result)
        self.assertEqual(UserGroupMembership.objects.count(), 5)
        members = get_memberships_of_users(user_group, [hamlet, othello, aaron])
        self.assertEqual(len(members), 3)

        # For normal testing we again login with hamlet
        self.logout()
        self.login(hamlet.email)
        # Test remove members
        params = {'delete': ujson.dumps([othello.id])}
        result = self.client_post('/json/user_groups/{}/members'.format(user_group.id),
                                  info=params)
        self.assert_json_success(result)
        self.assertEqual(UserGroupMembership.objects.count(), 4)
        members = get_memberships_of_users(user_group, [hamlet, othello, aaron])
        self.assertEqual(len(members), 2)

        # Test remove a member that's already removed
        params = {'delete': ujson.dumps([othello.id])}
        result = self.client_post('/json/user_groups/{}/members'.format(user_group.id),
                                  info=params)
        self.assert_json_error(result, "There is no member '6' in this user group")
        self.assertEqual(UserGroupMembership.objects.count(), 4)
        members = get_memberships_of_users(user_group, [hamlet, othello, aaron])
        self.assertEqual(len(members), 2)

        # Test when nothing is provided
        result = self.client_post('/json/user_groups/{}/members'.format(user_group.id),
                                  info={})
        msg = 'Nothing to do. Specify at least one of "add" or "delete".'
        self.assert_json_error(result, msg)

        # Test when user not a member of user group tries to remove members
        self.logout()
        self.login(cordelia.email)
        params = {'delete': ujson.dumps([hamlet.id])}
        result = self.client_post('/json/user_groups/{}/members'.format(user_group.id),
                                  info=params)
        self.assert_json_error(result, "Only group members and organization administrators can administer this group.")
        self.assertEqual(UserGroupMembership.objects.count(), 4)

        self.logout()
        # Test when organization admin tries to remove members from group
        iago = self.example_user('iago')
        self.login(iago.email)
        result = self.client_post('/json/user_groups/{}/members'.format(user_group.id),
                                  info=params)
        self.assert_json_success(result)
        self.assertEqual(UserGroupMembership.objects.count(), 3)
        members = get_memberships_of_users(user_group, [hamlet, othello, aaron])
        self.assertEqual(len(members), 1)
