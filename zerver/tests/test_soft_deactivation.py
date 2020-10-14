from unittest import mock

from django.utils.timezone import now as timezone_now

from zerver.lib.actions import do_add_alert_words
from zerver.lib.soft_deactivation import (
    add_missing_messages,
    do_auto_soft_deactivate_users,
    do_catch_up_soft_deactivated_users,
    do_soft_activate_users,
    do_soft_deactivate_user,
    do_soft_deactivate_users,
    get_soft_deactivated_users_for_catch_up,
    get_users_for_soft_deactivation,
    reactivate_user_if_soft_deactivated,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    get_subscription,
    get_user_messages,
    make_client,
    queries_captured,
)
from zerver.models import (
    Client,
    Message,
    RealmAuditLog,
    Stream,
    UserActivity,
    UserMessage,
    UserProfile,
    get_realm,
    get_stream,
)

logger_string = "zulip.soft_deactivation"

class UserSoftDeactivationTests(ZulipTestCase):

    def test_do_soft_deactivate_user(self) -> None:
        user = self.example_user('hamlet')
        self.assertFalse(user.long_term_idle)

        with self.assertLogs(logger_string, level="INFO") as m:
            do_soft_deactivate_user(user)
        self.assertEqual(m.output, [f"INFO:{logger_string}:Soft Deactivated user {user.id}"])

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
        self.send_huddle_message(users[0], users)

        with self.assertLogs(logger_string, level="INFO") as m:
            do_soft_deactivate_users(users)

        log_output = []
        for user in users:
            log_output.append(f"INFO:{logger_string}:Soft Deactivated user {user.id}")
        log_output.append(f"INFO:{logger_string}:Soft-deactivated batch of {len(users[:100])} users; {len(users[100:])} remain to process")

        self.assertEqual(m.output, log_output)

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
            self.example_user('desdemona'),
        ]
        client, _ = Client.objects.get_or_create(name='website')
        query = '/some/random/endpoint'
        last_visit = timezone_now()
        count = 150
        for user_profile in UserProfile.objects.all():
            UserActivity.objects.get_or_create(
                user_profile=user_profile,
                client=client,
                query=query,
                count=count,
                last_visit=last_visit,
            )
        filter_kwargs = dict(user_profile__realm=get_realm('zulip'))
        users_to_deactivate = get_users_for_soft_deactivation(-1, filter_kwargs)

        self.assert_length(users_to_deactivate, 9)
        for user in users_to_deactivate:
            self.assertTrue(user in users)

    def test_do_soft_activate_users(self) -> None:
        users = [
            self.example_user('hamlet'),
            self.example_user('iago'),
            self.example_user('cordelia'),
        ]
        self.send_huddle_message(users[0], users)

        with self.assertLogs(logger_string, level="INFO") as m:
            do_soft_deactivate_users(users)

        log_output = []
        for user in users:
            log_output.append(f"INFO:{logger_string}:Soft Deactivated user {user.id}")
        log_output.append(f"INFO:{logger_string}:Soft-deactivated batch of {len(users[:100])} users; {len(users[100:])} remain to process")

        self.assertEqual(m.output, log_output)

        for user in users:
            self.assertTrue(user.long_term_idle)

        with self.assertLogs(logger_string, level="INFO") as m:
            do_soft_activate_users(users)

        log_output = []
        for user in users:
            log_output.append(f"INFO:{logger_string}:Soft Reactivated user {user.id}")

        self.assertEqual(m.output, log_output)

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
            self.example_user('desdemona'),
        ]
        for user_profile in UserProfile.objects.all():
            user_profile.long_term_idle = True
            user_profile.save(update_fields=['long_term_idle'])

        filter_kwargs = dict(realm=get_realm('zulip'))
        users_to_catch_up = get_soft_deactivated_users_for_catch_up(filter_kwargs)

        self.assert_length(users_to_catch_up, 9)
        for user in users_to_catch_up:
            self.assertTrue(user in users)

    def test_do_catch_up_users(self) -> None:
        stream = 'Verona'
        hamlet = self.example_user('hamlet')
        users = [
            self.example_user('iago'),
            self.example_user('cordelia'),
        ]
        all_users = [*users, hamlet]
        for user in all_users:
            self.subscribe(user, stream)

        with self.assertLogs(logger_string, level="INFO") as m:
            do_soft_deactivate_users(users)

        log_output = []
        for user in users:
            log_output.append(f"INFO:{logger_string}:Soft Deactivated user {user.id}")
        log_output.append(f"INFO:{logger_string}:Soft-deactivated batch of {len(users[:100])} users; {len(users[100:])} remain to process")

        self.assertEqual(m.output, log_output)

        for user in users:
            self.assertTrue(user.long_term_idle)

        message_id = self.send_stream_message(hamlet, stream, 'Hello world!')
        already_received = UserMessage.objects.filter(message_id=message_id).count()

        with self.assertLogs(logger_string, level = "INFO") as m:
            do_catch_up_soft_deactivated_users(users)
        self.assertEqual(m.output, [f"INFO:{logger_string}:Caught up {len(users)} soft-deactivated users"])

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
            self.example_user('desdemona'),
        ]
        sender = self.example_user('hamlet')
        realm = get_realm('zulip')
        stream_name = 'announce'
        for user in [*users, sender]:
            self.subscribe(user, stream_name)

        client, _ = Client.objects.get_or_create(name='website')
        query = '/some/random/endpoint'
        last_visit = timezone_now()
        count = 150
        for user_profile in users:
            UserActivity.objects.get_or_create(
                user_profile=user_profile,
                client=client,
                query=query,
                count=count,
                last_visit=last_visit,
            )

        with self.assertLogs(logger_string, level="INFO") as m:
            users_deactivated = do_auto_soft_deactivate_users(-1, realm)

        log_output = []
        for user in users:
            log_output.append(f"INFO:{logger_string}:Soft Deactivated user {user.id}")
        log_output.append(f"INFO:{logger_string}:Soft-deactivated batch of {len(users[:100])} users; {len(users[100:])} remain to process")
        log_output.append(f"INFO:{logger_string}:Caught up {len(users)} soft-deactivated users")
        self.assertEqual(set(m.output), set(log_output))

        self.assert_length(users_deactivated, len(users))
        for user in users:
            self.assertTrue(user in users_deactivated)

        # Verify that deactivated users are caught up automatically

        message_id = self.send_stream_message(sender, stream_name)
        received_count = UserMessage.objects.filter(user_profile__in=users,
                                                    message_id=message_id).count()
        self.assertEqual(0, received_count)

        with self.assertLogs(logger_string, level="INFO") as m:
            users_deactivated = do_auto_soft_deactivate_users(-1, realm)

        log_output = []
        log_output.append(f"INFO:{logger_string}:Caught up {len(users)} soft-deactivated users")
        self.assertEqual(set(m.output), set(log_output))

        self.assert_length(users_deactivated, 0)   # all users are already deactivated
        received_count = UserMessage.objects.filter(user_profile__in=users,
                                                    message_id=message_id).count()
        self.assertEqual(len(users), received_count)

        # Verify that deactivated users are NOT caught up if
        # AUTO_CATCH_UP_SOFT_DEACTIVATED_USERS is off

        message_id = self.send_stream_message(sender, stream_name)
        received_count = UserMessage.objects.filter(user_profile__in=users,
                                                    message_id=message_id).count()
        self.assertEqual(0, received_count)

        with self.settings(AUTO_CATCH_UP_SOFT_DEACTIVATED_USERS=False):
            with self.assertLogs(logger_string, level="INFO") as m:
                users_deactivated = do_auto_soft_deactivate_users(-1, realm)
        self.assertEqual(m.output, [f"INFO:{logger_string}:Not catching up users since AUTO_CATCH_UP_SOFT_DEACTIVATED_USERS is off"])

        self.assert_length(users_deactivated, 0)   # all users are already deactivated
        received_count = UserMessage.objects.filter(user_profile__in=users,
                                                    message_id=message_id).count()
        self.assertEqual(0, received_count)


class SoftDeactivationMessageTest(ZulipTestCase):

    def test_reactivate_user_if_soft_deactivated(self) -> None:
        recipient_list  = [self.example_user("hamlet"), self.example_user("iago")]
        for user_profile in recipient_list:
            self.subscribe(user_profile, "Denmark")

        sender = self.example_user('iago')
        stream_name = 'Denmark'
        topic_name = 'foo'

        def last_realm_audit_log_entry(event_type: int) -> RealmAuditLog:
            return RealmAuditLog.objects.filter(
                event_type=event_type
            ).order_by('-event_time')[0]

        long_term_idle_user = self.example_user('hamlet')
        # We are sending this message to ensure that long_term_idle_user has
        # at least one UserMessage row.
        self.send_stream_message(long_term_idle_user, stream_name)
        with self.assertLogs(logger_string, level='INFO') as info_logs:
            do_soft_deactivate_users([long_term_idle_user])
        self.assertEqual(info_logs.output, [
            f'INFO:{logger_string}:Soft Deactivated user {long_term_idle_user.id}',
            f'INFO:{logger_string}:Soft-deactivated batch of 1 users; 0 remain to process'
        ])

        message = 'Test Message 1'
        message_id = self.send_stream_message(sender, stream_name,
                                              message, topic_name)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        idle_user_msg_count = len(idle_user_msg_list)
        self.assertNotEqual(idle_user_msg_list[-1].content, message)
        with queries_captured() as queries:
            reactivate_user_if_soft_deactivated(long_term_idle_user)
        self.assert_length(queries, 8)
        self.assertFalse(long_term_idle_user.long_term_idle)
        self.assertEqual(last_realm_audit_log_entry(
            RealmAuditLog.USER_SOFT_ACTIVATED).modified_user, long_term_idle_user)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count + 1)
        self.assertEqual(idle_user_msg_list[-1].content, message)
        long_term_idle_user.refresh_from_db()
        self.assertEqual(long_term_idle_user.last_active_message_id, message_id)

    def test_add_missing_messages(self) -> None:
        recipient_list  = [self.example_user("hamlet"), self.example_user("iago")]
        for user_profile in recipient_list:
            self.subscribe(user_profile, "Denmark")

        sender = self.example_user('iago')
        realm = sender.realm
        sending_client = make_client(name="test suite")
        stream_name = 'Denmark'
        stream = get_stream(stream_name, realm)
        topic_name = 'foo'

        def send_fake_message(message_content: str, stream: Stream) -> Message:
            recipient = stream.recipient
            message = Message(sender = sender,
                              recipient = recipient,
                              content = message_content,
                              date_sent = timezone_now(),
                              sending_client = sending_client)
            message.set_topic_name(topic_name)
            message.save()
            return message

        long_term_idle_user = self.example_user('hamlet')
        self.send_stream_message(long_term_idle_user, stream_name)
        with self.assertLogs(logger_string, level='INFO') as info_logs:
            do_soft_deactivate_users([long_term_idle_user])
        self.assertEqual(info_logs.output, [
            f'INFO:{logger_string}:Soft Deactivated user {long_term_idle_user.id}',
            f'INFO:{logger_string}:Soft-deactivated batch of 1 users; 0 remain to process'
        ])

        # Test that add_missing_messages() in simplest case of adding a
        # message for which UserMessage row doesn't exist for this user.
        sent_message = send_fake_message('Test Message 1', stream)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        idle_user_msg_count = len(idle_user_msg_list)
        self.assertNotEqual(idle_user_msg_list[-1], sent_message)
        with queries_captured() as queries:
            add_missing_messages(long_term_idle_user)
        self.assert_length(queries, 6)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count + 1)
        self.assertEqual(idle_user_msg_list[-1], sent_message)
        long_term_idle_user.refresh_from_db()
        self.assertEqual(long_term_idle_user.last_active_message_id, sent_message.id)

        # Test that add_missing_messages() only adds messages that aren't
        # already present in the UserMessage table. This test works on the
        # fact that previous test just above this added a message but didn't
        # updated the last_active_message_id field for the user.
        sent_message = send_fake_message('Test Message 2', stream)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        idle_user_msg_count = len(idle_user_msg_list)
        self.assertNotEqual(idle_user_msg_list[-1], sent_message)
        with queries_captured() as queries:
            add_missing_messages(long_term_idle_user)
        self.assert_length(queries, 7)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count + 1)
        self.assertEqual(idle_user_msg_list[-1], sent_message)
        long_term_idle_user.refresh_from_db()
        self.assertEqual(long_term_idle_user.last_active_message_id, sent_message.id)

        # Test UserMessage rows are created correctly in case of stream
        # Subscription was altered by admin while user was away.

        # Test for a public stream.
        sent_message_list = []
        sent_message_list.append(send_fake_message('Test Message 3', stream))
        # Alter subscription to stream.
        self.unsubscribe(long_term_idle_user, stream_name)
        send_fake_message('Test Message 4', stream)
        self.subscribe(long_term_idle_user, stream_name)
        sent_message_list.append(send_fake_message('Test Message 5', stream))
        sent_message_list.reverse()
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        idle_user_msg_count = len(idle_user_msg_list)
        for sent_message in sent_message_list:
            self.assertNotEqual(idle_user_msg_list.pop(), sent_message)
        with queries_captured() as queries:
            add_missing_messages(long_term_idle_user)
        self.assert_length(queries, 6)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count + 2)
        for sent_message in sent_message_list:
            self.assertEqual(idle_user_msg_list.pop(), sent_message)
        long_term_idle_user.refresh_from_db()
        self.assertEqual(long_term_idle_user.last_active_message_id, sent_message_list[0].id)

        # Test consecutive subscribe/unsubscribe in a public stream
        sent_message_list = []

        sent_message_list.append(send_fake_message('Test Message 6', stream))
        # Unsubscribe from stream and then immediately subscribe back again.
        self.unsubscribe(long_term_idle_user, stream_name)
        self.subscribe(long_term_idle_user, stream_name)
        sent_message_list.append(send_fake_message('Test Message 7', stream))
        # Again unsubscribe from stream and send a message.
        # This will make sure that if initially in a unsubscribed state
        # a consecutive subscribe/unsubscribe doesn't misbehave.
        self.unsubscribe(long_term_idle_user, stream_name)
        send_fake_message('Test Message 8', stream)
        # Do a subscribe and unsubscribe immediately.
        self.subscribe(long_term_idle_user, stream_name)
        self.unsubscribe(long_term_idle_user, stream_name)

        sent_message_list.reverse()
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        idle_user_msg_count = len(idle_user_msg_list)
        for sent_message in sent_message_list:
            self.assertNotEqual(idle_user_msg_list.pop(), sent_message)
        with queries_captured() as queries:
            add_missing_messages(long_term_idle_user)
        self.assert_length(queries, 6)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count + 2)
        for sent_message in sent_message_list:
            self.assertEqual(idle_user_msg_list.pop(), sent_message)
        long_term_idle_user.refresh_from_db()
        self.assertEqual(long_term_idle_user.last_active_message_id, sent_message_list[0].id)

        # Test for when user unsubscribes before soft deactivation
        # (must reactivate them in order to do this).

        do_soft_activate_users([long_term_idle_user])
        self.subscribe(long_term_idle_user, stream_name)
        # Send a real message to update last_active_message_id
        sent_message_id = self.send_stream_message(
            sender, stream_name, 'Test Message 9')
        self.unsubscribe(long_term_idle_user, stream_name)
        # Soft deactivate and send another message to the unsubscribed stream.
        with self.assertLogs(logger_string, level='INFO') as info_logs:
            do_soft_deactivate_users([long_term_idle_user])
        self.assertEqual(info_logs.output, [
            f'INFO:{logger_string}:Soft Deactivated user {long_term_idle_user.id}',
            f'INFO:{logger_string}:Soft-deactivated batch of 1 users; 0 remain to process'
        ])
        send_fake_message('Test Message 10', stream)

        idle_user_msg_list = get_user_messages(long_term_idle_user)
        idle_user_msg_count = len(idle_user_msg_list)
        self.assertEqual(idle_user_msg_list[-1].id, sent_message_id)
        with queries_captured() as queries:
            add_missing_messages(long_term_idle_user)
        # There are no streams to fetch missing messages from, so
        # the Message.objects query will be avoided.
        self.assert_length(queries, 4)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        # No new UserMessage rows should have been created.
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count)

        # Note: At this point in this test we have long_term_idle_user
        # unsubscribed from the 'Denmark' stream.

        # Test for a Private Stream.
        stream_name = "Core"
        private_stream = self.make_stream('Core', invite_only=True)
        self.subscribe(self.example_user("iago"), stream_name)
        sent_message_list = []
        send_fake_message('Test Message 11', private_stream)
        self.subscribe(self.example_user("hamlet"), stream_name)
        sent_message_list.append(send_fake_message('Test Message 12', private_stream))
        self.unsubscribe(long_term_idle_user, stream_name)
        send_fake_message('Test Message 13', private_stream)
        self.subscribe(long_term_idle_user, stream_name)
        sent_message_list.append(send_fake_message('Test Message 14', private_stream))
        sent_message_list.reverse()
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        idle_user_msg_count = len(idle_user_msg_list)
        for sent_message in sent_message_list:
            self.assertNotEqual(idle_user_msg_list.pop(), sent_message)
        with queries_captured() as queries:
            add_missing_messages(long_term_idle_user)
        self.assert_length(queries, 6)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count + 2)
        for sent_message in sent_message_list:
            self.assertEqual(idle_user_msg_list.pop(), sent_message)
        long_term_idle_user.refresh_from_db()
        self.assertEqual(long_term_idle_user.last_active_message_id, sent_message_list[0].id)

    @mock.patch('zerver.lib.soft_deactivation.BULK_CREATE_BATCH_SIZE', 2)
    def test_add_missing_messages_pagination(self) -> None:
        recipient_list  = [self.example_user("hamlet"), self.example_user("iago")]
        stream_name = 'Denmark'
        for user_profile in recipient_list:
            self.subscribe(user_profile, stream_name)

        sender = self.example_user('iago')
        long_term_idle_user = self.example_user('hamlet')
        self.send_stream_message(long_term_idle_user, stream_name)
        with self.assertLogs(logger_string, level='INFO') as info_logs:
            do_soft_deactivate_users([long_term_idle_user])
        self.assertEqual(info_logs.output, [
            f'INFO:{logger_string}:Soft Deactivated user {long_term_idle_user.id}',
            f'INFO:{logger_string}:Soft-deactivated batch of 1 users; 0 remain to process'
        ])

        num_new_messages = 5
        message_ids = []
        for _ in range(num_new_messages):
            message_id = self.send_stream_message(sender, stream_name)
            message_ids.append(message_id)

        idle_user_msg_list = get_user_messages(long_term_idle_user)
        idle_user_msg_count = len(idle_user_msg_list)
        with queries_captured() as queries:
            add_missing_messages(long_term_idle_user)
        self.assert_length(queries, 10)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count + num_new_messages)
        long_term_idle_user.refresh_from_db()
        self.assertEqual(long_term_idle_user.last_active_message_id, message_ids[-1])

    def test_user_message_filter(self) -> None:
        # In this test we are basically testing out the logic used out in
        # do_send_messages() in action.py for filtering the messages for which
        # UserMessage rows should be created for a soft-deactivated user.
        recipient_list  = [
            self.example_user("hamlet"),
            self.example_user("iago"),
            self.example_user('cordelia'),
        ]
        for user_profile in recipient_list:
            self.subscribe(user_profile, "Denmark")

        cordelia = self.example_user('cordelia')
        sender = self.example_user('iago')
        stream_name = 'Denmark'
        topic_name = 'foo'

        def send_stream_message(content: str) -> None:
            self.send_stream_message(sender, stream_name,
                                     content, topic_name)

        def send_personal_message(content: str) -> None:
            self.send_personal_message(sender, self.example_user("hamlet"), content)

        long_term_idle_user = self.example_user('hamlet')
        self.send_stream_message(long_term_idle_user, stream_name)
        with self.assertLogs(logger_string, level='INFO') as info_logs:
            do_soft_deactivate_users([long_term_idle_user])
        self.assertEqual(info_logs.output, [
            f'INFO:{logger_string}:Soft Deactivated user {long_term_idle_user.id}',
            f'INFO:{logger_string}:Soft-deactivated batch of 1 users; 0 remain to process'
        ])

        def assert_um_count(user: UserProfile, count: int) -> None:
            user_messages = get_user_messages(user)
            self.assertEqual(len(user_messages), count)

        def assert_last_um_content(user: UserProfile, content: str, negate: bool=False) -> None:
            user_messages = get_user_messages(user)
            if negate:
                self.assertNotEqual(user_messages[-1].content, content)
            else:
                self.assertEqual(user_messages[-1].content, content)

        # Test that sending a message to a stream with soft deactivated user
        # doesn't end up creating UserMessage row for deactivated user.
        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test Message 1'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, message, negate=True)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, message)

        # Test that sending a message to a stream with soft deactivated user
        # and push/email notifications on creates a UserMessage row for the
        # deactivated user.
        sub = get_subscription(stream_name, long_term_idle_user)
        sub.push_notifications = True
        sub.save()
        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test private stream message'
        send_stream_message(message)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count + 1)
        assert_last_um_content(long_term_idle_user, message)
        sub.push_notifications = False
        sub.save()

        # Test sending a private message to soft deactivated user creates
        # UserMessage row.
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test PM'
        send_personal_message(message)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count + 1)
        assert_last_um_content(long_term_idle_user, message)

        # Test UserMessage row is created while user is deactivated if
        # user itself is mentioned.
        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test @**King Hamlet** mention'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, message)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count + 1)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, message)

        # Test UserMessage row is not created while user is deactivated if
        # anyone is mentioned but the user.
        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test @**Cordelia Lear**  mention'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, message, negate=True)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, message)

        # Test UserMessage row is created while user is deactivated if
        # there is a wildcard mention such as @all or @everyone
        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test @**all** mention'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, message)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count + 1)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, message)

        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test @**everyone** mention'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, message)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count + 1)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, message)

        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test @**stream** mention'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, message)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count + 1)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, message)

        # Test UserMessage row is not created while user is deactivated if there
        # is a alert word in message.
        do_add_alert_words(long_term_idle_user, ['test_alert_word'])
        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Testing test_alert_word'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, message)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count + 1)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, message)

        # Test UserMessage row is created while user is deactivated if
        # message is a me message.
        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = '/me says test'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, message, negate=True)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, message)
