# -*- coding: utf-8 -*-
import ujson
import mock

from zerver.lib.actions import (
    ensure_stream,
)

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    most_recent_usermessage,
)
from zerver.lib.user_groups import (
    check_add_user_to_user_group,
    check_remove_user_from_user_group,
    create_user_group,
    get_user_groups,
    user_groups_in_realm,
    get_memberships_of_users,
    user_groups_in_realm_serialized,
)
from zerver.models import UserGroup, get_realm, Realm, \
    UserGroupMembership

class UserGroupTestCase(ZulipTestCase):
    def create_user_group_for_test(self, group_name: str,
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

    def test_user_group_get(self) -> None:
        # Test success
        user_profile = self.example_user('hamlet')
        self.login(user_profile.email)
        result = self.client_get('/json/user_groups')
        self.assert_json_success(result)
        self.assert_length(result.json()['user_groups'], UserGroup.objects.filter(realm=user_profile.realm).count())

    def test_user_group_create_by_guest_user(self) -> None:
        guest_user = self.example_user('polonius')

        # Guest users can't create user group
        self.login(guest_user.email)
        params = {
            'name': 'support',
            'members': ujson.dumps([guest_user.id]),
            'description': 'Support team',
        }
        result = self.client_post('/json/user_groups/create', info=params)
        self.assert_json_error(result, "Not allowed for guest users")

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

    def test_user_group_update_by_guest_user(self) -> None:
        hamlet = self.example_user('hamlet')
        guest_user = self.example_user('polonius')
        self.login(hamlet.email)
        params = {
            'name': 'support',
            'members': ujson.dumps([hamlet.id, guest_user.id]),
            'description': 'Support team',
        }
        result = self.client_post('/json/user_groups/create', info=params)
        self.assert_json_success(result)
        user_group = UserGroup.objects.get(name='support')

        # Guest user can't edit any detail of an user group
        self.login(guest_user.email)
        params = {
            'name': 'help',
            'description': 'Troubleshooting team',
        }
        result = self.client_patch('/json/user_groups/{}'.format(user_group.id), info=params)
        self.assert_json_error(result, "Not allowed for guest users")

    def test_user_group_update_to_already_existing_name(self) -> None:
        hamlet = self.example_user('hamlet')
        self.login(hamlet.email)
        realm = get_realm('zulip')
        support_user_group = create_user_group('support', [hamlet], realm)
        marketing_user_group = create_user_group('marketing', [hamlet], realm)

        params = {
            'name': marketing_user_group.name,
        }
        result = self.client_patch('/json/user_groups/{}'.format(support_user_group.id), info=params)
        self.assert_json_error(
            result, "User group '{}' already exists.".format(marketing_user_group.name))

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

    def test_user_group_delete_by_guest_user(self) -> None:
        hamlet = self.example_user('hamlet')
        guest_user = self.example_user('polonius')
        self.login(hamlet.email)
        params = {
            'name': 'support',
            'members': ujson.dumps([hamlet.id, guest_user.id]),
            'description': 'Support team',
        }
        result = self.client_post('/json/user_groups/create', info=params)
        self.assert_json_success(result)
        user_group = UserGroup.objects.get(name='support')

        # Guest users can't delete any user group(not even those of which they are a member)
        self.login(guest_user.email)
        result = self.client_delete('/json/user_groups/{}'.format(user_group.id))
        self.assert_json_error(result, "Not allowed for guest users")

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

    def test_mentions(self) -> None:
        cordelia = self.example_user('cordelia')
        hamlet = self.example_user('hamlet')
        othello = self.example_user('othello')
        zoe = self.example_user('ZOE')

        realm = cordelia.realm

        group_name = 'support'
        stream_name = 'Dev Help'

        content_with_group_mention = 'hey @*support* can you help us with this?'

        ensure_stream(realm, stream_name)

        all_users = {cordelia, hamlet, othello, zoe}
        support_team = {hamlet, zoe}
        sender = cordelia
        other_users = all_users - support_team

        for user in all_users:
            self.subscribe(user, stream_name)

        create_user_group(
            name=group_name,
            members=list(support_team),
            realm=realm,
        )

        payload = dict(
            type="stream",
            to=stream_name,
            sender=sender.email,
            client='test suite',
            topic='whatever',
            content=content_with_group_mention,
        )

        with mock.patch('logging.info'):
            result = self.api_post(sender.email, "/json/messages", payload)

        self.assert_json_success(result)

        for user in support_team:
            um = most_recent_usermessage(user)
            self.assertTrue(um.flags.mentioned)

        for user in other_users:
            um = most_recent_usermessage(user)
            self.assertFalse(um.flags.mentioned)
