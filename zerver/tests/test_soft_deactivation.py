# -*- coding: utf-8 -*-

import mock

from django.utils.timezone import now as timezone_now

from zerver.lib.soft_deactivation import (
    do_soft_deactivate_user,
    do_soft_deactivate_users,
    get_users_for_soft_deactivation,
    do_soft_activate_users,
    get_soft_deactivated_users_for_catch_up,
    do_catch_up_soft_deactivated_users,
    do_auto_soft_deactivate_users
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import (
    Client, UserProfile, UserActivity, get_realm, UserMessage
)

class UserSoftDeactivationTests(ZulipTestCase):

    def test_do_soft_deactivate_user(self) -> None:
        user = self.example_user('hamlet')
        self.assertFalse(user.long_term_idle)

        with mock.patch('logging.info'):
            do_soft_deactivate_user(user)

        user.refresh_from_db()
        self.assertTrue(user.long_term_idle)

    def test_do_soft_deactivate_users(self) -> None:
        users = [
            self.example_user('hamlet'),
            self.example_user('iago'),
            self.example_user('cordelia'),
        ]
        for user in users:
            self.assertFalse(user.long_term_idle)

        # We are sending this message to ensure that users have at least
        # one UserMessage row.
        self.send_huddle_message(users[0].email,
                                 [user.email for user in users])

        with mock.patch('logging.info'):
            do_soft_deactivate_users(users)

        for user in users:
            user.refresh_from_db()
            self.assertTrue(user.long_term_idle)

    def test_get_users_for_soft_deactivation(self) -> None:
        users = [
            self.example_user('hamlet'),
            self.example_user('iago'),
            self.example_user('cordelia'),
            self.example_user('ZOE'),
            self.example_user('othello'),
            self.example_user('prospero'),
            self.example_user('aaron'),
            self.example_user('polonius'),
        ]
        client, _ = Client.objects.get_or_create(name='website')
        query = '/json/users/me/pointer'
        last_visit = timezone_now()
        count = 150
        for user_profile in UserProfile.objects.all():
            UserActivity.objects.get_or_create(
                user_profile=user_profile,
                client=client,
                query=query,
                count=count,
                last_visit=last_visit
            )
        filter_kwargs = dict(user_profile__realm=get_realm('zulip'))
        users_to_deactivate = get_users_for_soft_deactivation(-1, filter_kwargs)

        self.assert_length(users_to_deactivate, 8)
        for user in users_to_deactivate:
            self.assertTrue(user in users)

    def test_do_soft_activate_users(self) -> None:
        users = [
            self.example_user('hamlet'),
            self.example_user('iago'),
            self.example_user('cordelia'),
        ]
        self.send_huddle_message(users[0].email,
                                 [user.email for user in users])
        with mock.patch('logging.info'):
            do_soft_deactivate_users(users)
        for user in users:
            self.assertTrue(user.long_term_idle)

        with mock.patch('logging.info'):
            do_soft_activate_users(users)

        for user in users:
            user.refresh_from_db()
            self.assertFalse(user.long_term_idle)

    def test_get_users_for_catch_up(self) -> None:
        users = [
            self.example_user('hamlet'),
            self.example_user('iago'),
            self.example_user('cordelia'),
            self.example_user('ZOE'),
            self.example_user('othello'),
            self.example_user('prospero'),
            self.example_user('aaron'),
            self.example_user('polonius'),
        ]
        for user_profile in UserProfile.objects.all():
            user_profile.long_term_idle = True
            user_profile.save(update_fields=['long_term_idle'])

        filter_kwargs = dict(realm=get_realm('zulip'))
        users_to_catch_up = get_soft_deactivated_users_for_catch_up(filter_kwargs)

        self.assert_length(users_to_catch_up, 8)
        for user in users_to_catch_up:
            self.assertTrue(user in users)

    def test_do_catch_up_users(self) -> None:
        stream = 'Verona'
        hamlet = self.example_user('hamlet')
        users = [
            self.example_user('iago'),
            self.example_user('cordelia'),
        ]
        all_users = users + [hamlet]
        for user in all_users:
            self.subscribe(user, stream)

        with mock.patch('logging.info'):
            do_soft_deactivate_users(users)
        for user in users:
            self.assertTrue(user.long_term_idle)

        message_id = self.send_stream_message(hamlet.email, stream, 'Hello world!')
        already_received = UserMessage.objects.filter(message_id=message_id).count()
        with mock.patch('logging.info'):
            do_catch_up_soft_deactivated_users(users)
        catch_up_received = UserMessage.objects.filter(message_id=message_id).count()
        self.assertEqual(already_received + len(users), catch_up_received)

        for user in users:
            user.refresh_from_db()
            self.assertTrue(user.long_term_idle)
            self.assertEqual(user.last_active_message_id, message_id)

    def test_do_auto_soft_deactivate_users(self) -> None:
        users = [
            self.example_user('iago'),
            self.example_user('cordelia'),
            self.example_user('ZOE'),
            self.example_user('othello'),
            self.example_user('prospero'),
            self.example_user('aaron'),
            self.example_user('polonius'),
        ]
        sender = self.example_user('hamlet')
        realm = get_realm('zulip')
        stream_name = 'announce'
        for user in users + [sender]:
            self.subscribe(user, stream_name)

        client, _ = Client.objects.get_or_create(name='website')
        query = '/json/users/me/pointer'
        last_visit = timezone_now()
        count = 150
        for user_profile in users:
            UserActivity.objects.get_or_create(
                user_profile=user_profile,
                client=client,
                query=query,
                count=count,
                last_visit=last_visit
            )

        with mock.patch('logging.info'):
            users_deactivated = do_auto_soft_deactivate_users(-1, realm)
        self.assert_length(users_deactivated, len(users))
        for user in users:
            self.assertTrue(user in users_deactivated)

        # Verify that deactivated users are caught up automatically

        message_id = self.send_stream_message(sender.email, stream_name)
        received_count = UserMessage.objects.filter(user_profile__in=users,
                                                    message_id=message_id).count()
        self.assertEqual(0, received_count)

        with mock.patch('logging.info'):
            users_deactivated = do_auto_soft_deactivate_users(-1, realm)

        self.assert_length(users_deactivated, 0)   # all users are already deactivated
        received_count = UserMessage.objects.filter(user_profile__in=users,
                                                    message_id=message_id).count()
        self.assertEqual(len(users), received_count)

        # Verify that deactivated users are NOT caught up if
        # AUTO_CATCH_UP_SOFT_DEACTIVATED_USERS is off

        message_id = self.send_stream_message(sender.email, stream_name)
        received_count = UserMessage.objects.filter(user_profile__in=users,
                                                    message_id=message_id).count()
        self.assertEqual(0, received_count)

        with self.settings(AUTO_CATCH_UP_SOFT_DEACTIVATED_USERS=False):
            with mock.patch('logging.info'):
                users_deactivated = do_auto_soft_deactivate_users(-1, realm)

        self.assert_length(users_deactivated, 0)   # all users are already deactivated
        received_count = UserMessage.objects.filter(user_profile__in=users,
                                                    message_id=message_id).count()
        self.assertEqual(0, received_count)
