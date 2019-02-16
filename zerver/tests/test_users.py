# -*- coding: utf-8 -*-

from typing import (Any, Dict, Iterable, List, Mapping,
                    Optional, TypeVar, Union)

from zerver.lib.test_helpers import (
    queries_captured, simulated_empty_cache,
    tornado_redirected_to_list, get_subscription,
    most_recent_message,
)
from zerver.lib.test_classes import (
    ZulipTestCase,
)

from zerver.models import UserProfile, Recipient, \
    RealmDomain, UserHotspot, \
    get_user, get_realm, get_stream, get_stream_recipient, \
    get_source_profile, \
    ScheduledEmail, check_valid_user_ids, \
    get_user_by_id_in_realm_including_cross_realm, CustomProfileField

from zerver.lib.avatar import avatar_url
from zerver.lib.exceptions import JsonableError
from zerver.lib.send_email import send_future_email
from zerver.lib.actions import (
    get_emails_from_user_ids,
    get_recipient_info,
    do_deactivate_user,
    do_reactivate_user,
    do_change_is_admin,
    do_create_user,
)
from zerver.lib.create_user import copy_user_settings
from zerver.lib.topic_mutes import add_topic_mute
from zerver.lib.stream_topic import StreamTopicTarget
from zerver.lib.users import user_ids_to_users, access_user_by_id, \
    get_accounts_for_email

import datetime
import mock
import ujson

K = TypeVar('K')
V = TypeVar('V')
def find_dict(lst: Iterable[Dict[K, V]], k: K, v: V) -> Dict[K, V]:
    for dct in lst:
        if dct[k] == v:
            return dct
    raise AssertionError('Cannot find element in list where key %s == %s' % (k, v))

class PermissionTest(ZulipTestCase):
    def test_do_change_is_admin(self) -> None:
        """
        Ensures change_is_admin raises an AssertionError when invalid permissions
        are provided to it.
        """

        # this should work fine
        user_profile = self.example_user('hamlet')
        do_change_is_admin(user_profile, True)

        # this should work a-ok as well
        do_change_is_admin(user_profile, True, permission='administer')

        # this should "fail" with an AssertionError
        with self.assertRaises(AssertionError):
            do_change_is_admin(user_profile, True, permission='totally-not-valid-perm')

    def test_get_admin_users(self) -> None:
        user_profile = self.example_user('hamlet')
        do_change_is_admin(user_profile, False)
        admin_users = user_profile.realm.get_admin_users()
        self.assertFalse(user_profile in admin_users)
        do_change_is_admin(user_profile, True)
        admin_users = user_profile.realm.get_admin_users()
        self.assertTrue(user_profile in admin_users)

    def test_updating_non_existent_user(self) -> None:
        self.login(self.example_email("hamlet"))
        admin = self.example_user('hamlet')
        do_change_is_admin(admin, True)

        invalid_user_id = 1000
        result = self.client_patch('/json/users/{}'.format(invalid_user_id), {})
        self.assert_json_error(result, 'No such user')

    def test_admin_api(self) -> None:
        self.login(self.example_email("hamlet"))
        admin = self.example_user('hamlet')
        user = self.example_user('othello')
        realm = admin.realm
        do_change_is_admin(admin, True)

        # Make sure we see is_admin flag in /json/users
        result = self.client_get('/json/users')
        self.assert_json_success(result)
        members = result.json()['members']
        hamlet = find_dict(members, 'email', self.example_email("hamlet"))
        self.assertTrue(hamlet['is_admin'])
        othello = find_dict(members, 'email', self.example_email("othello"))
        self.assertFalse(othello['is_admin'])

        # Giveth
        req = dict(is_admin=ujson.dumps(True))

        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.client_patch('/json/users/{}'.format(self.example_user("othello").id), req)
        self.assert_json_success(result)
        admin_users = realm.get_admin_users()
        self.assertTrue(user in admin_users)
        person = events[0]['event']['person']
        self.assertEqual(person['email'], self.example_email("othello"))
        self.assertEqual(person['is_admin'], True)

        # Taketh away
        req = dict(is_admin=ujson.dumps(False))
        events = []
        with tornado_redirected_to_list(events):
            result = self.client_patch('/json/users/{}'.format(self.example_user("othello").id), req)
        self.assert_json_success(result)
        admin_users = realm.get_admin_users()
        self.assertFalse(user in admin_users)
        person = events[0]['event']['person']
        self.assertEqual(person['email'], self.example_email("othello"))
        self.assertEqual(person['is_admin'], False)

        # Cannot take away from last admin
        self.login(self.example_email("iago"))
        req = dict(is_admin=ujson.dumps(False))
        events = []
        with tornado_redirected_to_list(events):
            result = self.client_patch('/json/users/{}'.format(self.example_user("hamlet").id), req)
        self.assert_json_success(result)
        admin_users = realm.get_admin_users()
        self.assertFalse(admin in admin_users)
        person = events[0]['event']['person']
        self.assertEqual(person['email'], self.example_email("hamlet"))
        self.assertEqual(person['is_admin'], False)
        with tornado_redirected_to_list([]):
            result = self.client_patch('/json/users/{}'.format(self.example_user("iago").id), req)
        self.assert_json_error(result, 'Cannot remove the only organization administrator')

        # Make sure only admins can patch other user's info.
        self.login(self.example_email("othello"))
        result = self.client_patch('/json/users/{}'.format(self.example_user("hamlet").id), req)
        self.assert_json_error(result, 'Insufficient permission')

    def test_user_cannot_promote_to_admin(self) -> None:
        self.login(self.example_email("hamlet"))
        req = dict(is_admin=ujson.dumps(True))
        result = self.client_patch('/json/users/{}'.format(self.example_user('hamlet').id), req)
        self.assert_json_error(result, 'Insufficient permission')

    def test_admin_user_can_change_full_name(self) -> None:
        new_name = 'new name'
        self.login(self.example_email("iago"))
        hamlet = self.example_user('hamlet')
        req = dict(full_name=ujson.dumps(new_name))
        result = self.client_patch('/json/users/{}'.format(hamlet.id), req)
        self.assert_json_success(result)
        hamlet = self.example_user('hamlet')
        self.assertEqual(hamlet.full_name, new_name)
        req['is_admin'] = ujson.dumps(False)
        result = self.client_patch('/json/users/{}'.format(hamlet.id), req)
        self.assert_json_success(result)

    def test_non_admin_cannot_change_full_name(self) -> None:
        self.login(self.example_email("hamlet"))
        req = dict(full_name=ujson.dumps('new name'))
        result = self.client_patch('/json/users/{}'.format(self.example_user('othello').id), req)
        self.assert_json_error(result, 'Insufficient permission')

    def test_admin_cannot_set_long_full_name(self) -> None:
        new_name = 'a' * (UserProfile.MAX_NAME_LENGTH + 1)
        self.login(self.example_email("iago"))
        req = dict(full_name=ujson.dumps(new_name))
        result = self.client_patch('/json/users/{}'.format(self.example_user('hamlet').id), req)
        self.assert_json_error(result, 'Name too long!')

    def test_admin_cannot_set_short_full_name(self) -> None:
        new_name = 'a'
        self.login(self.example_email("iago"))
        req = dict(full_name=ujson.dumps(new_name))
        result = self.client_patch('/json/users/{}'.format(self.example_user('hamlet').id), req)
        self.assert_json_error(result, 'Name too short!')

    def test_admin_cannot_set_full_name_with_invalid_characters(self) -> None:
        new_name = 'Opheli*'
        self.login(self.example_email("iago"))
        req = dict(full_name=ujson.dumps(new_name))
        result = self.client_patch('/json/users/{}'.format(self.example_user('hamlet').id), req)
        self.assert_json_error(result, 'Invalid characters in name!')

    def test_access_user_by_id(self) -> None:
        iago = self.example_user("iago")

        # Must be a valid user ID in the realm
        with self.assertRaises(JsonableError):
            access_user_by_id(iago, 1234)
        with self.assertRaises(JsonableError):
            access_user_by_id(iago, self.mit_user("sipbtest").id)

        # Can only access bot users if allow_deactivated is passed
        bot = self.example_user("welcome_bot")
        access_user_by_id(iago, bot.id, allow_bots=True)
        with self.assertRaises(JsonableError):
            access_user_by_id(iago, bot.id)

        # Can only access deactivated users if allow_deactivated is passed
        hamlet = self.example_user("hamlet")
        do_deactivate_user(hamlet)
        with self.assertRaises(JsonableError):
            access_user_by_id(iago, hamlet.id)
        access_user_by_id(iago, hamlet.id, allow_deactivated=True)

        # Non-admin user can't admin another user
        with self.assertRaises(JsonableError):
            access_user_by_id(self.example_user("cordelia"), self.example_user("aaron").id)

    def test_change_regular_member_to_guest(self) -> None:
        iago = self.example_user("iago")
        self.login(iago.email)

        hamlet = self.example_user("hamlet")
        self.assertFalse(hamlet.is_guest)

        # Test failure of making user both admin and guest
        req = dict(is_guest=ujson.dumps(True), is_admin=ujson.dumps(True))
        result = self.client_patch('/json/users/{}'.format(hamlet.id), req)
        self.assert_json_error(result, 'Guests cannot be organization administrators')
        self.assertFalse(hamlet.is_guest)
        self.assertFalse(hamlet.is_realm_admin)
        hamlet = self.example_user("hamlet")

        req = dict(is_guest=ujson.dumps(True))
        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.client_patch('/json/users/{}'.format(hamlet.id), req)
        self.assert_json_success(result)

        hamlet = self.example_user("hamlet")
        self.assertTrue(hamlet.is_guest)
        person = events[0]['event']['person']
        self.assertEqual(person['email'], hamlet.email)
        self.assertTrue(person['is_guest'])

    def test_change_guest_to_regular_member(self) -> None:
        iago = self.example_user("iago")
        self.login(iago.email)

        polonius = self.example_user("polonius")
        self.assertTrue(polonius.is_guest)
        req = dict(is_guest=ujson.dumps(False))
        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.client_patch('/json/users/{}'.format(polonius.id), req)
        self.assert_json_success(result)

        polonius = self.example_user("polonius")
        self.assertFalse(polonius.is_guest)
        person = events[0]['event']['person']
        self.assertEqual(person['email'], polonius.email)
        self.assertFalse(person['is_guest'])

    def test_change_admin_to_guest(self) -> None:
        iago = self.example_user("iago")
        self.login(iago.email)
        hamlet = self.example_user("hamlet")
        do_change_is_admin(hamlet, True)
        self.assertFalse(hamlet.is_guest)
        self.assertTrue(hamlet.is_realm_admin)

        # Test failure of making a admin to guest without revoking admin status
        req = dict(is_guest=ujson.dumps(True))
        result = self.client_patch('/json/users/{}'.format(hamlet.id), req)
        self.assert_json_error(result, 'Guests cannot be organization administrators')

        # Test changing a user from admin to guest and revoking admin status
        hamlet = self.example_user("hamlet")
        self.assertFalse(hamlet.is_guest)
        req = dict(is_admin=ujson.dumps(False), is_guest=ujson.dumps(True))
        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.client_patch('/json/users/{}'.format(hamlet.id), req)
        self.assert_json_success(result)

        hamlet = self.example_user("hamlet")
        self.assertTrue(hamlet.is_guest)
        self.assertFalse(hamlet.is_realm_admin)

        person = events[0]['event']['person']
        self.assertEqual(person['email'], hamlet.email)
        self.assertFalse(person['is_admin'])

        person = events[1]['event']['person']
        self.assertEqual(person['email'], hamlet.email)
        self.assertTrue(person['is_guest'])

    def test_change_guest_to_admin(self) -> None:
        iago = self.example_user("iago")
        self.login(iago.email)
        polonius = self.example_user("polonius")
        self.assertTrue(polonius.is_guest)
        self.assertFalse(polonius.is_realm_admin)

        # Test failure of making a guest to admin without revoking guest status
        req = dict(is_admin=ujson.dumps(True))
        result = self.client_patch('/json/users/{}'.format(polonius.id), req)
        self.assert_json_error(result, 'Guests cannot be organization administrators')

        # Test changing a user from guest to admin and revoking guest status
        polonius = self.example_user("polonius")
        self.assertFalse(polonius.is_realm_admin)
        req = dict(is_admin=ujson.dumps(True), is_guest=ujson.dumps(False))
        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.client_patch('/json/users/{}'.format(polonius.id), req)
        self.assert_json_success(result)

        polonius = self.example_user("polonius")
        self.assertFalse(polonius.is_guest)
        self.assertTrue(polonius.is_realm_admin)

        person = events[0]['event']['person']
        self.assertEqual(person['email'], polonius.email)
        self.assertTrue(person['is_admin'])

        person = events[1]['event']['person']
        self.assertEqual(person['email'], polonius.email)
        self.assertFalse(person['is_guest'])

    def test_admin_user_can_change_profile_data(self) -> None:
        realm = get_realm('zulip')
        self.login(self.example_email("iago"))
        new_profile_data = []
        cordelia = self.example_user("cordelia")

        # Test for all type of data
        fields = {
            'Phone number': 'short text data',
            'Biography': 'long text data',
            'Favorite food': 'short text data',
            'Favorite editor': 'vim',
            'Birthday': '1909-3-5',
            'GitHub profile': 'https://github.com/ABC',
            'Mentor': [cordelia.id],
        }

        for field_name in fields:
            field = CustomProfileField.objects.get(name=field_name, realm=realm)
            new_profile_data.append({
                'id': field.id,
                'value': fields[field_name],
            })

        result = self.client_patch('/json/users/{}'.format(cordelia.id),
                                   {'profile_data': ujson.dumps(new_profile_data)})
        self.assert_json_success(result)

        cordelia = self.example_user("cordelia")
        for field_dict in cordelia.profile_data:
            with self.subTest(field_name=field_dict['name']):
                self.assertEqual(field_dict['value'], fields[field_dict['name']])  # type: ignore # Reason in comment
            # Invalid index type for dict key, it must be str but field_dict values can be anything

        # Test admin user cannot set invalid profile data
        invalid_fields = [
            ('Favorite editor', 'invalid choice', "'invalid choice' is not a valid choice for 'Favorite editor'."),
            ('Birthday', '1909-34-55', "Birthday is not a date"),
            ('GitHub profile', 'not url', "GitHub profile is not a URL"),
            ('Mentor', "not list of user ids", "User IDs is not a list"),
        ]

        for field_name, field_value, error_msg in invalid_fields:
            new_profile_data = []
            field = CustomProfileField.objects.get(name=field_name, realm=realm)
            new_profile_data.append({
                'id': field.id,
                'value': field_value,
            })

            result = self.client_patch('/json/users/{}'.format(cordelia.id),
                                       {'profile_data': ujson.dumps(new_profile_data)})
            self.assert_json_error(result, error_msg)

        # non-existant field and no data
        invalid_profile_data = [{
            'id': 9001,
            'value': ''
        }]
        result = self.client_patch('/json/users/{}'.format(cordelia.id),
                                   {'profile_data': ujson.dumps(invalid_profile_data)})
        self.assert_json_error(result, 'Field id 9001 not found.')

        # non-existant field and data
        invalid_profile_data = [{
            'id': 9001,
            'value': 'some data'
        }]
        result = self.client_patch('/json/users/{}'.format(cordelia.id),
                                   {'profile_data': ujson.dumps(invalid_profile_data)})
        self.assert_json_error(result, 'Field id 9001 not found.')

        # Test for clearing/resetting field values.
        empty_profile_data = []
        for field_name in fields:
            field = CustomProfileField.objects.get(name=field_name, realm=realm)
            value = ''  # type: Union[str, None, List[Any]]
            if field.field_type == CustomProfileField.USER:
                value = []
            empty_profile_data.append({
                'id': field.id,
                'value': value,
            })
        result = self.client_patch('/json/users/{}'.format(cordelia.id),
                                   {'profile_data': ujson.dumps(empty_profile_data)})
        self.assert_json_success(result)
        for field_dict in cordelia.profile_data:
            with self.subTest(field_name=field_dict['name']):
                self.assertEqual(field_dict['value'], None)

        # Test adding some of the field values after removing all.
        hamlet = self.example_user("hamlet")
        new_fields = {
            'Phone number': None,
            'Biography': 'A test user',
            'Favorite food': None,
            'Favorite editor': None,
            'Birthday': None,
            'GitHub profile': 'https://github.com/DEF',
            'Mentor': [hamlet.id]
        }
        new_profile_data = []
        for field_name in fields:
            field = CustomProfileField.objects.get(name=field_name, realm=realm)
            value = None
            if new_fields[field_name]:
                value = new_fields[field_name]
            new_profile_data.append({
                'id': field.id,
                'value': value,
            })
        result = self.client_patch('/json/users/{}'.format(cordelia.id),
                                   {'profile_data': ujson.dumps(new_profile_data)})
        self.assert_json_success(result)
        for field_dict in cordelia.profile_data:
            with self.subTest(field_name=field_dict['name']):
                self.assertEqual(field_dict['value'], new_fields[str(field_dict['name'])])

    def test_non_admin_user_cannot_change_profile_data(self) -> None:
        self.login(self.example_email("cordelia"))
        hamlet = self.example_user("hamlet")
        realm = get_realm("zulip")

        new_profile_data = []
        field = CustomProfileField.objects.get(name="Biography", realm=realm)
        new_profile_data.append({
            'id': field.id,
            'value': "New hamlet Biography",
        })
        result = self.client_patch('/json/users/{}'.format(hamlet.id),
                                   {'profile_data': ujson.dumps(new_profile_data)})
        self.assert_json_error(result, 'Insufficient permission')

        result = self.client_patch('/json/users/{}'.format(self.example_user("cordelia").id),
                                   {'profile_data': ujson.dumps(new_profile_data)})
        self.assert_json_error(result, 'Insufficient permission')

class AdminCreateUserTest(ZulipTestCase):
    def test_create_user_backend(self) -> None:

        # This test should give us complete coverage on
        # create_user_backend.  It mostly exercises error
        # conditions, and it also does a basic test of the success
        # path.

        admin = self.example_user('hamlet')
        admin_email = admin.email
        realm = admin.realm
        self.login(admin_email)
        do_change_is_admin(admin, True)

        result = self.client_post("/json/users", dict())
        self.assert_json_error(result, "Missing 'email' argument")

        result = self.client_post("/json/users", dict(
            email='romeo@not-zulip.com',
        ))
        self.assert_json_error(result, "Missing 'password' argument")

        result = self.client_post("/json/users", dict(
            email='romeo@not-zulip.com',
            password='xxxx',
        ))
        self.assert_json_error(result, "Missing 'full_name' argument")

        result = self.client_post("/json/users", dict(
            email='romeo@not-zulip.com',
            password='xxxx',
            full_name='Romeo Montague',
        ))
        self.assert_json_error(result, "Missing 'short_name' argument")

        result = self.client_post("/json/users", dict(
            email='broken',
            password='xxxx',
            full_name='Romeo Montague',
            short_name='Romeo',
        ))
        self.assert_json_error(result, "Bad name or username")

        result = self.client_post("/json/users", dict(
            email='romeo@not-zulip.com',
            password='xxxx',
            full_name='Romeo Montague',
            short_name='Romeo',
        ))
        self.assert_json_error(result,
                               "Email 'romeo@not-zulip.com' not allowed in this organization")

        RealmDomain.objects.create(realm=get_realm('zulip'), domain='zulip.net')
        valid_params = dict(
            email='romeo@zulip.net',
            password='xxxx',
            full_name='Romeo Montague',
            short_name='Romeo',
        )
        result = self.client_post("/json/users", valid_params)
        self.assert_json_success(result)

        # Romeo is a newly registered user
        new_user = get_user('romeo@zulip.net', get_realm('zulip'))
        self.assertEqual(new_user.full_name, 'Romeo Montague')
        self.assertEqual(new_user.short_name, 'Romeo')

        # we can't create the same user twice.
        result = self.client_post("/json/users", valid_params)
        self.assert_json_error(result,
                               "Email 'romeo@zulip.net' already in use")

        # Don't allow user to sign up with disposable email.
        realm.emails_restricted_to_domains = False
        realm.disallow_disposable_email_addresses = True
        realm.save()

        valid_params["email"] = "abc@mailnator.com"
        result = self.client_post("/json/users", valid_params)
        self.assert_json_error(result, "Disposable email addresses are not allowed in this organization")

        # Don't allow creating a user with + in their email address when realm
        # is restricted to a domain.
        realm.emails_restricted_to_domains = True
        realm.save()

        valid_params["email"] = "iago+label@zulip.com"
        result = self.client_post("/json/users", valid_params)
        self.assert_json_error(result, "Email addresses containing + are not allowed.")

        # Users can be created with + in their email address when realm
        # is not restricted to a domain.
        realm.emails_restricted_to_domains = False
        realm.save()

        valid_params["email"] = "iago+label@zulip.com"
        result = self.client_post("/json/users", valid_params)
        self.assert_json_success(result)

class UserProfileTest(ZulipTestCase):
    def test_get_emails_from_user_ids(self) -> None:
        hamlet = self.example_user('hamlet')
        othello = self.example_user('othello')
        dct = get_emails_from_user_ids([hamlet.id, othello.id])
        self.assertEqual(dct[hamlet.id], self.example_email("hamlet"))
        self.assertEqual(dct[othello.id], self.example_email("othello"))

    def test_valid_user_id(self) -> None:
        realm = get_realm("zulip")
        hamlet = self.example_user('hamlet')
        othello = self.example_user('othello')
        bot = self.example_user("welcome_bot")

        # Invalid user ID
        invalid_uid = 1000  # type: Any
        self.assertEqual(check_valid_user_ids(realm.id, invalid_uid),
                         "User IDs is not a list")
        self.assertEqual(check_valid_user_ids(realm.id, [invalid_uid]),
                         "Invalid user ID: %d" % (invalid_uid))

        invalid_uid = "abc"
        self.assertEqual(check_valid_user_ids(realm.id, [invalid_uid]),
                         "User IDs[0] is not an integer")
        invalid_uid = str(othello.id)
        self.assertEqual(check_valid_user_ids(realm.id, [invalid_uid]),
                         "User IDs[0] is not an integer")

        # User is in different realm
        self.assertEqual(check_valid_user_ids(get_realm("zephyr").id, [hamlet.id]),
                         "Invalid user ID: %d" % (hamlet.id))

        # User is not active
        hamlet.is_active = False
        hamlet.save()
        self.assertEqual(check_valid_user_ids(realm.id, [hamlet.id]),
                         "User with ID %d is deactivated" % (hamlet.id))
        self.assertEqual(check_valid_user_ids(realm.id, [hamlet.id], allow_deactivated=True),
                         None)

        # User is a bot
        self.assertEqual(check_valid_user_ids(realm.id, [bot.id]),
                         "User with ID %d is a bot" % (bot.id))

        # Succesfully get non-bot, active user belong to your realm
        self.assertEqual(check_valid_user_ids(realm.id, [othello.id]), None)

    def test_cache_invalidation(self) -> None:
        hamlet = self.example_user('hamlet')
        with mock.patch('zerver.lib.cache.delete_display_recipient_cache') as m:
            hamlet.full_name = 'Hamlet Junior'
            hamlet.save(update_fields=["full_name"])

        self.assertTrue(m.called)

        with mock.patch('zerver.lib.cache.delete_display_recipient_cache') as m:
            hamlet.long_term_idle = True
            hamlet.save(update_fields=["long_term_idle"])

        self.assertFalse(m.called)

    def test_user_ids_to_users(self) -> None:
        real_user_ids = [
            self.example_user('hamlet').id,
            self.example_user('cordelia').id,
        ]

        self.assertEqual(user_ids_to_users([], get_realm("zulip")), [])
        self.assertEqual(set([user_profile.id for user_profile in user_ids_to_users(real_user_ids, get_realm("zulip"))]),
                         set(real_user_ids))
        with self.assertRaises(JsonableError):
            user_ids_to_users([1234], get_realm("zephyr"))
        with self.assertRaises(JsonableError):
            user_ids_to_users(real_user_ids, get_realm("zephyr"))

    def test_bulk_get_users(self) -> None:
        from zerver.lib.users import bulk_get_users
        hamlet = self.example_email("hamlet")
        cordelia = self.example_email("cordelia")
        webhook_bot = self.example_email("webhook_bot")
        result = bulk_get_users([hamlet, cordelia], get_realm("zulip"))
        self.assertEqual(result[hamlet].email, hamlet)
        self.assertEqual(result[cordelia].email, cordelia)

        result = bulk_get_users([hamlet, cordelia, webhook_bot], None,
                                base_query=UserProfile.objects.all())
        self.assertEqual(result[hamlet].email, hamlet)
        self.assertEqual(result[cordelia].email, cordelia)
        self.assertEqual(result[webhook_bot].email, webhook_bot)

    def test_get_accounts_for_email(self) -> None:
        def check_account_present_in_accounts(user: UserProfile, accounts: List[Dict[str, Optional[str]]]) -> None:
            for account in accounts:
                realm = user.realm
                if account["avatar"] == avatar_url(user) and account["full_name"] == user.full_name \
                        and account["realm_name"] == realm.name and account["string_id"] == realm.string_id:
                    return
            raise AssertionError("Account not found")

        lear_realm = get_realm("lear")
        cordelia_in_zulip = self.example_user("cordelia")
        cordelia_in_lear = get_user("cordelia@zulip.com", lear_realm)

        email = "cordelia@zulip.com"
        accounts = get_accounts_for_email(email)
        self.assert_length(accounts, 2)
        check_account_present_in_accounts(cordelia_in_zulip, accounts)
        check_account_present_in_accounts(cordelia_in_lear, accounts)

        email = "CORDelia@zulip.com"
        accounts = get_accounts_for_email(email)
        self.assert_length(accounts, 2)
        check_account_present_in_accounts(cordelia_in_zulip, accounts)
        check_account_present_in_accounts(cordelia_in_lear, accounts)

        email = "IAGO@ZULIP.COM"
        accounts = get_accounts_for_email(email)
        self.assert_length(accounts, 1)
        check_account_present_in_accounts(self.example_user("iago"), accounts)

    def test_get_source_profile(self) -> None:
        iago = get_source_profile("iago@zulip.com", "zulip")
        assert iago is not None
        self.assertEqual(iago.email, "iago@zulip.com")
        self.assertEqual(iago.realm, get_realm("zulip"))

        iago = get_source_profile("IAGO@ZULIP.com", "zulip")
        assert iago is not None
        self.assertEqual(iago.email, "iago@zulip.com")

        cordelia = get_source_profile("cordelia@zulip.com", "lear")
        assert cordelia is not None
        self.assertEqual(cordelia.email, "cordelia@zulip.com")

        self.assertIsNone(get_source_profile("iagod@zulip.com", "zulip"))
        self.assertIsNone(get_source_profile("iago@zulip.com", "ZULIP"))
        self.assertIsNone(get_source_profile("iago@zulip.com", "lear"))

    def test_copy_user_settings(self) -> None:
        iago = self.example_user("iago")
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")

        cordelia.default_language = "de"
        cordelia.emojiset = "apple"
        cordelia.timezone = "America/Phoenix"
        cordelia.night_mode = True
        cordelia.enable_offline_email_notifications = False
        cordelia.enable_stream_push_notifications = True
        cordelia.enter_sends = False
        cordelia.save()

        UserHotspot.objects.filter(user=cordelia).delete()
        UserHotspot.objects.filter(user=iago).delete()
        hotspots_completed = ['intro_reply', 'intro_streams', 'intro_topics']
        for hotspot in hotspots_completed:
            UserHotspot.objects.create(user=cordelia, hotspot=hotspot)

        copy_user_settings(cordelia, iago)

        # We verify that cordelia and iago match, but hamlet has the defaults.
        self.assertEqual(iago.full_name, "Cordelia Lear")
        self.assertEqual(cordelia.full_name, "Cordelia Lear")
        self.assertEqual(hamlet.full_name, "King Hamlet")

        self.assertEqual(iago.default_language, "de")
        self.assertEqual(cordelia.default_language, "de")
        self.assertEqual(hamlet.default_language, "en")

        self.assertEqual(iago.emojiset, "apple")
        self.assertEqual(cordelia.emojiset, "apple")
        self.assertEqual(hamlet.emojiset, "google-blob")

        self.assertEqual(iago.timezone, "America/Phoenix")
        self.assertEqual(cordelia.timezone, "America/Phoenix")
        self.assertEqual(hamlet.timezone, "")

        self.assertEqual(iago.night_mode, True)
        self.assertEqual(cordelia.night_mode, True)
        self.assertEqual(hamlet.night_mode, False)

        self.assertEqual(iago.enable_offline_email_notifications, False)
        self.assertEqual(cordelia.enable_offline_email_notifications, False)
        self.assertEqual(hamlet.enable_offline_email_notifications, True)

        self.assertEqual(iago.enable_stream_push_notifications, True)
        self.assertEqual(cordelia.enable_stream_push_notifications, True)
        self.assertEqual(hamlet.enable_stream_push_notifications, False)

        self.assertEqual(iago.enter_sends, False)
        self.assertEqual(cordelia.enter_sends, False)
        self.assertEqual(hamlet.enter_sends, True)

        hotspots = list(UserHotspot.objects.filter(user=iago).values_list('hotspot', flat=True))
        self.assertEqual(hotspots, hotspots_completed)

    def test_get_user_by_id_in_realm_including_cross_realm(self) -> None:
        realm = get_realm('zulip')
        hamlet = self.example_user('hamlet')
        othello = self.example_user('othello')
        bot = self.example_user('welcome_bot')

        # Pass in the ID of a cross-realm bot and a valid realm
        cross_realm_bot = get_user_by_id_in_realm_including_cross_realm(
            bot.id, realm)
        self.assertEqual(cross_realm_bot.email, bot.email)
        self.assertEqual(cross_realm_bot.id, bot.id)

        # Pass in the ID of a cross-realm bot but with a invalid realm,
        # note that the realm should be irrelevant here
        cross_realm_bot = get_user_by_id_in_realm_including_cross_realm(
            bot.id, get_realm('invalid'))
        self.assertEqual(cross_realm_bot.email, bot.email)
        self.assertEqual(cross_realm_bot.id, bot.id)

        # Pass in the ID of a non-cross-realm user with a realm
        user_profile = get_user_by_id_in_realm_including_cross_realm(
            othello.id, realm)
        self.assertEqual(user_profile.email, othello.email)
        self.assertEqual(user_profile.id, othello.id)

        # If the realm doesn't match, or if the ID is not that of a
        # cross-realm bot, UserProfile.DoesNotExist is raised
        with self.assertRaises(UserProfile.DoesNotExist):
            get_user_by_id_in_realm_including_cross_realm(
                hamlet.id, get_realm('invalid'))

class ActivateTest(ZulipTestCase):
    def test_basics(self) -> None:
        user = self.example_user('hamlet')
        do_deactivate_user(user)
        self.assertFalse(user.is_active)
        do_reactivate_user(user)
        self.assertTrue(user.is_active)

    def test_api(self) -> None:
        admin = self.example_user('othello')
        do_change_is_admin(admin, True)
        self.login(self.example_email("othello"))

        user = self.example_user('hamlet')
        self.assertTrue(user.is_active)

        result = self.client_delete('/json/users/{}'.format(user.id))
        self.assert_json_success(result)
        user = self.example_user('hamlet')
        self.assertFalse(user.is_active)

        result = self.client_post('/json/users/{}/reactivate'.format(user.id))
        self.assert_json_success(result)
        user = self.example_user('hamlet')
        self.assertTrue(user.is_active)

    def test_api_with_nonexistent_user(self) -> None:
        admin = self.example_user('othello')
        do_change_is_admin(admin, True)
        self.login(self.example_email("othello"))

        # Cannot deactivate a user with the bot api
        result = self.client_delete('/json/bots/{}'.format(self.example_user("hamlet").id))
        self.assert_json_error(result, 'No such bot')

        # Cannot deactivate a nonexistent user.
        invalid_user_id = 1000
        result = self.client_delete('/json/users/{}'.format(invalid_user_id))
        self.assert_json_error(result, 'No such user')

        result = self.client_delete('/json/users/{}'.format(self.example_user("webhook_bot").id))
        self.assert_json_error(result, 'No such user')

        result = self.client_delete('/json/users/{}'.format(self.example_user("iago").id))
        self.assert_json_success(result)

        result = self.client_delete('/json/users/{}'.format(admin.id))
        self.assert_json_error(result, 'Cannot deactivate the only organization administrator')

        # Cannot reactivate a nonexistent user.
        invalid_user_id = 1000
        result = self.client_post('/json/users/{}/reactivate'.format(invalid_user_id))
        self.assert_json_error(result, 'No such user')

    def test_api_with_insufficient_permissions(self) -> None:
        non_admin = self.example_user('othello')
        do_change_is_admin(non_admin, False)
        self.login(self.example_email("othello"))

        # Cannot deactivate a user with the users api
        result = self.client_delete('/json/users/{}'.format(self.example_user("hamlet").id))
        self.assert_json_error(result, 'Insufficient permission')

        # Cannot reactivate a user
        result = self.client_post('/json/users/{}/reactivate'.format(self.example_user("hamlet").id))
        self.assert_json_error(result, 'Insufficient permission')

    def test_clear_scheduled_jobs(self) -> None:
        user = self.example_user('hamlet')
        send_future_email('zerver/emails/followup_day1', user.realm,
                          to_user_ids=[user.id], delay=datetime.timedelta(hours=1))
        self.assertEqual(ScheduledEmail.objects.count(), 1)
        do_deactivate_user(user)
        self.assertEqual(ScheduledEmail.objects.count(), 0)

class RecipientInfoTest(ZulipTestCase):
    def test_stream_recipient_info(self) -> None:
        hamlet = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')
        othello = self.example_user('othello')

        realm = hamlet.realm

        stream_name = 'Test Stream'
        topic_name = 'test topic'

        for user in [hamlet, cordelia, othello]:
            self.subscribe(user, stream_name)

        stream = get_stream(stream_name, realm)
        recipient = get_stream_recipient(stream.id)

        stream_topic = StreamTopicTarget(
            stream_id=stream.id,
            topic_name=topic_name,
        )

        sub = get_subscription(stream_name, hamlet)
        sub.push_notifications = True
        sub.save()

        info = get_recipient_info(
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
        )

        all_user_ids = {hamlet.id, cordelia.id, othello.id}

        expected_info = dict(
            active_user_ids=all_user_ids,
            push_notify_user_ids=set(),
            stream_push_user_ids={hamlet.id},
            stream_email_user_ids=set(),
            um_eligible_user_ids=all_user_ids,
            long_term_idle_user_ids=set(),
            default_bot_user_ids=set(),
            service_bot_tuples=[],
        )

        self.assertEqual(info, expected_info)

        # Now mute Hamlet to omit him from stream_push_user_ids.
        add_topic_mute(
            user_profile=hamlet,
            stream_id=stream.id,
            recipient_id=recipient.id,
            topic_name=topic_name,
        )

        info = get_recipient_info(
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
        )

        self.assertEqual(info['stream_push_user_ids'], set())

        # Add a service bot.
        service_bot = do_create_user(
            email='service-bot@zulip.com',
            password='',
            realm=realm,
            full_name='',
            short_name='',
            bot_type=UserProfile.EMBEDDED_BOT,
        )

        info = get_recipient_info(
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
            possibly_mentioned_user_ids={service_bot.id}
        )
        self.assertEqual(info['service_bot_tuples'], [
            (service_bot.id, UserProfile.EMBEDDED_BOT),
        ])

        # Add a normal bot.
        normal_bot = do_create_user(
            email='normal-bot@zulip.com',
            password='',
            realm=realm,
            full_name='',
            short_name='',
            bot_type=UserProfile.DEFAULT_BOT,
        )

        info = get_recipient_info(
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
            possibly_mentioned_user_ids={service_bot.id, normal_bot.id}
        )
        self.assertEqual(info['default_bot_user_ids'], {normal_bot.id})

    def test_get_recipient_info_invalid_recipient_type(self) -> None:
        hamlet = self.example_user('hamlet')
        realm = hamlet.realm

        stream = get_stream('Rome', realm)
        stream_topic = StreamTopicTarget(
            stream_id=stream.id,
            topic_name='test topic',
        )

        # Make sure get_recipient_info asserts on invalid recipient types
        with self.assertRaisesRegex(ValueError, 'Bad recipient type'):
            invalid_recipient = Recipient(type=999)  # 999 is not a valid type
            get_recipient_info(
                recipient=invalid_recipient,
                sender_id=hamlet.id,
                stream_topic=stream_topic,
            )

class BulkUsersTest(ZulipTestCase):
    def test_client_gravatar_option(self) -> None:
        self.login(self.example_email('cordelia'))

        hamlet = self.example_user('hamlet')

        def get_hamlet_avatar(client_gravatar: bool) -> Optional[str]:
            data = dict(client_gravatar=ujson.dumps(client_gravatar))
            result = self.client_get('/json/users', data)
            self.assert_json_success(result)
            rows = result.json()['members']
            hamlet_data = [
                row for row in rows
                if row['user_id'] == hamlet.id
            ][0]
            return hamlet_data['avatar_url']

        self.assertEqual(
            get_hamlet_avatar(client_gravatar=True),
            None
        )

        '''
        The main purpose of this test is to make sure we
        return None for avatar_url when client_gravatar is
        set to True.  And we do a sanity check for when it's
        False, but we leave it to other tests to validate
        the specific URL.
        '''
        self.assertIn(
            'gravatar.com',
            get_hamlet_avatar(client_gravatar=False),
        )

class GetProfileTest(ZulipTestCase):

    def common_update_pointer(self, email: str, pointer: int) -> None:
        self.login(email)
        result = self.client_post("/json/users/me/pointer", {"pointer": pointer})
        self.assert_json_success(result)

    def common_get_profile(self, user_id: str) -> Dict[str, Any]:
        # Assumes all users are example users in realm 'zulip'
        user_profile = self.example_user(user_id)
        self.send_stream_message(user_profile.email, "Verona", "hello")

        result = self.api_get(user_profile.email, "/api/v1/users/me")

        max_id = most_recent_message(user_profile).id

        self.assert_json_success(result)
        json = result.json()

        self.assertIn("client_id", json)
        self.assertIn("max_message_id", json)
        self.assertIn("pointer", json)

        self.assertEqual(json["max_message_id"], max_id)
        return json

    def test_get_pointer(self) -> None:
        email = self.example_email("hamlet")
        self.login(email)
        result = self.client_get("/json/users/me/pointer")
        self.assert_json_success(result)
        self.assertIn("pointer", result.json())

    def test_cache_behavior(self) -> None:
        """Tests whether fetching a user object the normal way, with
        `get_user`, makes 1 cache query and 1 database query.
        """
        realm = get_realm("zulip")
        email = self.example_email("hamlet")
        with queries_captured() as queries:
            with simulated_empty_cache() as cache_queries:
                user_profile = get_user(email, realm)

        self.assert_length(queries, 1)
        self.assert_length(cache_queries, 1)
        self.assertEqual(user_profile.email, email)

    def test_get_user_profile(self) -> None:
        self.login(self.example_email("hamlet"))
        result = ujson.loads(self.client_get('/json/users/me').content)
        self.assertEqual(result['short_name'], 'hamlet')
        self.assertEqual(result['email'], self.example_email("hamlet"))
        self.assertEqual(result['full_name'], 'King Hamlet')
        self.assertIn("user_id", result)
        self.assertFalse(result['is_bot'])
        self.assertFalse(result['is_admin'])
        self.login(self.example_email("iago"))
        result = ujson.loads(self.client_get('/json/users/me').content)
        self.assertEqual(result['short_name'], 'iago')
        self.assertEqual(result['email'], self.example_email("iago"))
        self.assertEqual(result['full_name'], 'Iago')
        self.assertFalse(result['is_bot'])
        self.assertTrue(result['is_admin'])

    def test_api_get_empty_profile(self) -> None:
        """
        Ensure GET /users/me returns a max message id and returns successfully
        """
        json = self.common_get_profile("othello")
        self.assertEqual(json["pointer"], -1)

    def test_profile_with_pointer(self) -> None:
        """
        Ensure GET /users/me returns a proper pointer id after the pointer is updated
        """

        id1 = self.send_stream_message(self.example_email("othello"), "Verona")
        id2 = self.send_stream_message(self.example_email("othello"), "Verona")

        json = self.common_get_profile("hamlet")

        self.common_update_pointer(self.example_email("hamlet"), id2)
        json = self.common_get_profile("hamlet")
        self.assertEqual(json["pointer"], id2)

        self.common_update_pointer(self.example_email("hamlet"), id1)
        json = self.common_get_profile("hamlet")
        self.assertEqual(json["pointer"], id2)  # pointer does not move backwards

        result = self.client_post("/json/users/me/pointer", {"pointer": 99999999})
        self.assert_json_error(result, "Invalid message ID")

    def test_get_all_profiles_avatar_urls(self) -> None:
        user_profile = self.example_user('hamlet')
        result = self.api_get(self.example_email("hamlet"), "/api/v1/users")
        self.assert_json_success(result)

        for user in result.json()['members']:
            if user['email'] == self.example_email("hamlet"):
                self.assertEqual(
                    user['avatar_url'],
                    avatar_url(user_profile),
                )
