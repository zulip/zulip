import datetime
import time
from typing import List
from unittest import mock

from django.test import override_settings
from django.utils.timezone import now as timezone_now

from confirmation.models import one_click_unsubscribe_link
from zerver.lib.actions import do_create_user
from zerver.lib.digest import (
    _enqueue_emails_for_realm,
    bulk_handle_digest_email,
    bulk_write_realm_audit_logs,
    enqueue_emails,
    gather_new_streams,
    handle_digest_email,
    streams_recently_modified_for_user,
)
from zerver.lib.message import get_last_message_id
from zerver.lib.streams import create_stream_if_needed
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import cache_tries_captured, queries_captured
from zerver.models import (
    Message,
    Realm,
    RealmAuditLog,
    Stream,
    UserActivity,
    UserProfile,
    flush_per_request_caches,
    get_client,
    get_realm,
    get_stream,
)


class TestDigestEmailMessages(ZulipTestCase):

    @mock.patch('zerver.lib.digest.enough_traffic')
    @mock.patch('zerver.lib.digest.send_future_email')
    def test_multiple_stream_senders(self,
                                     mock_send_future_email: mock.MagicMock,
                                     mock_enough_traffic: mock.MagicMock) -> None:

        othello = self.example_user('othello')
        self.subscribe(othello, 'Verona')

        one_day_ago = timezone_now() - datetime.timedelta(days=1)
        Message.objects.all().update(date_sent=one_day_ago)
        one_hour_ago = timezone_now() - datetime.timedelta(seconds=3600)

        cutoff = time.mktime(one_hour_ago.timetuple())

        senders = ['hamlet', 'cordelia',  'iago', 'prospero', 'ZOE']
        self.simulate_stream_conversation('Verona', senders)

        flush_per_request_caches()
        # When this test is run in isolation, one additional query is run which
        # is equivalent to
        # ContentType.objects.get(app_label='zerver', model='userprofile')
        # This code is run when we call `confirmation.models.create_confirmation_link`.
        # To trigger this, we call the one_click_unsubscribe_link function below.
        one_click_unsubscribe_link(othello, 'digest')
        with queries_captured() as queries:
            handle_digest_email(othello.id, cutoff)

        self.assert_length(queries, 9)

        self.assertEqual(mock_send_future_email.call_count, 1)
        kwargs = mock_send_future_email.call_args[1]
        self.assertEqual(kwargs['to_user_ids'], [othello.id])

        hot_convo = kwargs['context']['hot_conversations'][0]

        expected_participants = {
            self.example_user(sender).full_name
            for sender in senders
        }

        self.assertEqual(set(hot_convo['participants']), expected_participants)
        self.assertEqual(hot_convo['count'], 5 - 2)  # 5 messages, but 2 shown
        teaser_messages = hot_convo['first_few_messages'][0]['senders']
        self.assertIn('some content', teaser_messages[0]['content'][0]['plain'])
        self.assertIn(teaser_messages[0]['sender'], expected_participants)

    @mock.patch('zerver.lib.digest.enough_traffic')
    @mock.patch('zerver.lib.digest.send_future_email')
    def test_guest_user_multiple_stream_sender(self,
                                               mock_send_future_email: mock.MagicMock,
                                               mock_enough_traffic: mock.MagicMock) -> None:
        othello = self.example_user('othello')
        hamlet = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')
        polonius = self.example_user('polonius')
        create_stream_if_needed(cordelia.realm, 'web_public_stream', is_web_public=True)
        self.subscribe(othello, 'web_public_stream')
        self.subscribe(hamlet, 'web_public_stream')
        self.subscribe(cordelia, 'web_public_stream')
        self.subscribe(polonius, 'web_public_stream')

        one_day_ago = timezone_now() - datetime.timedelta(days=1)
        Message.objects.all().update(date_sent=one_day_ago)
        one_hour_ago = timezone_now() - datetime.timedelta(seconds=3600)

        cutoff = time.mktime(one_hour_ago.timetuple())

        senders = ['hamlet', 'cordelia',  'othello', 'desdemona']
        self.simulate_stream_conversation('web_public_stream', senders)

        flush_per_request_caches()
        # When this test is run in isolation, one additional query is run which
        # is equivalent to
        # ContentType.objects.get(app_label='zerver', model='userprofile')
        # This code is run when we call `confirmation.models.create_confirmation_link`.
        # To trigger this, we call the one_click_unsubscribe_link function below.
        one_click_unsubscribe_link(polonius, 'digest')
        with queries_captured() as queries:
            handle_digest_email(polonius.id, cutoff)

        self.assert_length(queries, 9)

        self.assertEqual(mock_send_future_email.call_count, 1)
        kwargs = mock_send_future_email.call_args[1]
        self.assertEqual(kwargs['to_user_ids'], [polonius.id])

        new_stream_names = kwargs['context']['new_streams']['plain']
        self.assertTrue('web_public_stream' in new_stream_names)

    def test_soft_deactivated_user_multiple_stream_senders(self) -> None:
        one_day_ago = timezone_now() - datetime.timedelta(days=1)
        Message.objects.all().update(date_sent=one_day_ago)

        digest_users = [
            self.example_user('othello'),
            self.example_user('aaron'),
            self.example_user('desdemona'),
            self.example_user('polonius'),
        ]

        for digest_user in digest_users:
            for stream in ['Verona', 'Scotland', 'Denmark']:
                self.subscribe(digest_user, stream)

        RealmAuditLog.objects.all().delete()

        for digest_user in digest_users:
            digest_user.long_term_idle = True
            digest_user.save(update_fields=['long_term_idle'])

        # Send messages to a stream and unsubscribe - subscribe from that stream
        senders = ['hamlet', 'cordelia',  'iago', 'prospero', 'ZOE']
        self.simulate_stream_conversation('Verona', senders)

        for digest_user in digest_users:
            self.unsubscribe(digest_user, 'Verona')
            self.subscribe(digest_user, 'Verona')

        # Send messages to other streams
        self.simulate_stream_conversation('Scotland', senders)
        self.simulate_stream_conversation('Denmark', senders)

        one_hour_ago = timezone_now() - datetime.timedelta(seconds=3600)
        cutoff = time.mktime(one_hour_ago.timetuple())

        flush_per_request_caches()

        # When this test is run in isolation, one additional query is run which
        # is equivalent to
        # ContentType.objects.get(app_label='zerver', model='userprofile')
        # This code is run when we call `confirmation.models.create_confirmation_link`.
        # To trigger this, we call the one_click_unsubscribe_link function below.
        one_click_unsubscribe_link(digest_users[0], 'digest')

        with mock.patch('zerver.lib.digest.send_future_email') as mock_send_future_email:
            digest_user_ids = [user.id for user in digest_users]

            with queries_captured() as queries:
                with cache_tries_captured() as cache_tries:
                    bulk_handle_digest_email(digest_user_ids, cutoff)

            self.assert_length(queries, 39)
            self.assert_length(cache_tries, 4)

        self.assertEqual(mock_send_future_email.call_count, len(digest_users))

        for i, digest_user in enumerate(digest_users):
            kwargs = mock_send_future_email.call_args_list[i][1]
            self.assertEqual(kwargs['to_user_ids'], [digest_user.id])

            hot_conversations = kwargs['context']['hot_conversations']
            self.assertEqual(2, len(hot_conversations), [digest_user.id])

            hot_convo = hot_conversations[0]
            expected_participants = {
                self.example_user(sender).full_name
                for sender in senders
            }

            self.assertEqual(set(hot_convo['participants']), expected_participants)
            self.assertEqual(hot_convo['count'], 5 - 2)  # 5 messages, but 2 shown
            teaser_messages = hot_convo['first_few_messages'][0]['senders']
            self.assertIn('some content', teaser_messages[0]['content'][0]['plain'])
            self.assertIn(teaser_messages[0]['sender'], expected_participants)

        last_message_id = get_last_message_id()
        for digest_user in digest_users:
            log_rows = RealmAuditLog.objects.filter(
                modified_user_id=digest_user.id,
                event_type=RealmAuditLog.USER_DIGEST_EMAIL_CREATED,
            )
            (log,) = log_rows
            self.assertEqual(log.event_last_message_id, last_message_id)

    def test_streams_recently_modified_for_user(self) -> None:
        othello = self.example_user('othello')
        cordelia = self.example_user('cordelia')

        for stream in ['Verona', 'Scotland', 'Denmark']:
            self.subscribe(othello, stream)
            self.subscribe(cordelia, stream)

        realm = othello.realm
        denmark = get_stream('Denmark', realm)
        verona = get_stream('Verona', realm)

        two_hours_ago = timezone_now() - datetime.timedelta(hours=2)
        one_hour_ago = timezone_now() - datetime.timedelta(hours=1)

        # Delete all RealmAuditLogs to start with a clean slate.
        RealmAuditLog.objects.all().delete()

        # Unsubscribe and subscribe Othello from a stream
        self.unsubscribe(othello, 'Denmark')
        self.subscribe(othello, 'Denmark')

        self.assertEqual(
            streams_recently_modified_for_user(othello, one_hour_ago),
            {denmark.id}
        )

        # Backdate all our logs (so that Denmark will no longer
        # appear like a recently modified stream for Othello).
        RealmAuditLog.objects.all().update(event_time=two_hours_ago)

        # Now Denmark no longer appears recent to Othello.
        self.assertEqual(
            streams_recently_modified_for_user(othello, one_hour_ago),
            set()
        )

        # Unsubscribe and subscribe from a stream
        self.unsubscribe(othello, 'Verona')
        self.subscribe(othello, 'Verona')

        # Now, Verona, but not Denmark, appears recent.
        self.assertEqual(
            streams_recently_modified_for_user(othello, one_hour_ago),
            {verona.id},
        )

        # make sure we don't mix up Othello and Cordelia
        self.unsubscribe(cordelia, 'Denmark')
        self.subscribe(cordelia, 'Denmark')

        self.assertEqual(
            streams_recently_modified_for_user(cordelia, one_hour_ago),
            {denmark.id}
        )

    def active_human_users(self, realm: Realm) -> List[UserProfile]:
        users = list(UserProfile.objects.filter(
            realm=realm,
            is_active=True,
            is_bot=False,
            enable_digest_emails=True,
        ))

        assert len(users) >= 5

        return users

    def test_twelve_hour_exemption(self) -> None:
        RealmAuditLog.objects.all().delete()

        realm = get_realm('zulip')

        cutoff = timezone_now() - datetime.timedelta(days=5)

        with mock.patch('zerver.lib.digest.queue_digest_recipient') as queue_mock:
            _enqueue_emails_for_realm(realm, cutoff)

        users = self.active_human_users(realm)

        self.assertEqual(queue_mock.call_count, len(users))

        # Simulate that we have sent digests for all our users.
        bulk_write_realm_audit_logs(users)

        # Now if we run again, we won't get any users, since they will have
        # recent RealmAuditLog rows.
        with mock.patch('zerver.lib.digest.queue_digest_recipient') as queue_mock:
            _enqueue_emails_for_realm(realm, cutoff)

        self.assertEqual(queue_mock.call_count, 0)

    @override_settings(SEND_DIGEST_EMAILS=True)
    def test_inactive_users_queued_for_digest(self) -> None:
        UserActivity.objects.all().delete()
        RealmAuditLog.objects.all().delete()
        # Turn on realm digest emails for all realms
        Realm.objects.update(digest_emails_enabled=True)
        cutoff = timezone_now() - datetime.timedelta(days=5)

        realm = get_realm("zulip")
        users = self.active_human_users(realm)

        # Check that all users without an a UserActivity entry are considered
        # inactive users and get enqueued.
        with mock.patch('zerver.lib.digest.queue_digest_recipient') as queue_mock:
            _enqueue_emails_for_realm(realm, cutoff)

        self.assertEqual(queue_mock.call_count, len(users))

        for user in users:
            last_visit = timezone_now() - datetime.timedelta(days=1)
            UserActivity.objects.create(
                last_visit=last_visit,
                user_profile=user,
                count=0,
                client=get_client("test_client"),
            )

        # Now we expect no users, due to recent activity.
        with mock.patch('zerver.lib.digest.queue_digest_recipient') as queue_mock:
            _enqueue_emails_for_realm(realm, cutoff)

        self.assertEqual(queue_mock.call_count, 0)

        # Now, backdate all our users activity.
        last_visit = timezone_now() - datetime.timedelta(days=7)
        UserActivity.objects.all().update(last_visit=last_visit)

        with mock.patch('zerver.lib.digest.queue_digest_recipient') as queue_mock:
            _enqueue_emails_for_realm(realm, cutoff)

        self.assertEqual(queue_mock.call_count, len(users))

    def tuesday(self) -> datetime.datetime:
        return datetime.datetime(year=2016, month=1, day=5, tzinfo=datetime.timezone.utc)

    @override_settings(SEND_DIGEST_EMAILS=False)
    def test_disabled(self) -> None:
        RealmAuditLog.objects.all().delete()

        tuesday = self.tuesday()
        cutoff = tuesday - datetime.timedelta(days=5)

        with mock.patch("zerver.lib.digest.timezone_now", return_value=tuesday):
            with mock.patch("zerver.lib.digest.queue_digest_recipient") as queue_mock:
                enqueue_emails(cutoff)
        queue_mock.assert_not_called()

    @override_settings(SEND_DIGEST_EMAILS=True)
    def test_only_enqueue_on_valid_day(self) -> None:
        RealmAuditLog.objects.all().delete()

        not_tuesday = datetime.datetime(year=2016, month=1, day=6, tzinfo=datetime.timezone.utc)
        cutoff = not_tuesday - datetime.timedelta(days=5)

        with mock.patch("zerver.lib.digest.timezone_now", return_value=not_tuesday):
            with mock.patch("zerver.lib.digest.queue_digest_recipient") as queue_mock:
                enqueue_emails(cutoff)
        queue_mock.assert_not_called()

    @override_settings(SEND_DIGEST_EMAILS=True)
    def test_no_email_digest_for_bots(self) -> None:
        RealmAuditLog.objects.all().delete()

        cutoff = timezone_now() - datetime.timedelta(days=5)

        realm = get_realm('zulip')
        realm.digest_emails_enabled = True
        realm.save()

        bot = do_create_user(
            'some_bot@example.com',
            'password',
            realm,
            'some_bot',
            bot_type=UserProfile.DEFAULT_BOT,
        )

        # Check that bots are not sent emails
        with mock.patch('zerver.lib.digest.queue_digest_recipient') as queue_mock:
            _enqueue_emails_for_realm(realm, cutoff)

        assert queue_mock.call_count >= 5

        for arg in queue_mock.call_args_list:
            user = arg[0][0]
            self.assertNotEqual(user.id, bot.id)

    @override_settings(SEND_DIGEST_EMAILS=True)
    def test_new_stream_link(self) -> None:
        Stream.objects.all().delete()
        cutoff = timezone_now() - datetime.timedelta(days=5)
        cordelia = self.example_user('cordelia')
        stream = create_stream_if_needed(cordelia.realm, 'New stream')[0]
        stream.date_created = timezone_now()
        stream.save()

        stream_count, stream_info = gather_new_streams(cordelia, cutoff)
        self.assertEqual(stream_count, 1)
        expected_html = f"<a href='http://zulip.testserver/#narrow/stream/{stream.id}-New-stream'>New stream</a>"
        self.assertEqual(stream_info['html'][0], expected_html)

        # Make the stream appear to be older.
        stream.date_created = timezone_now() - datetime.timedelta(days=7)
        stream.save()

        stream_count, stream_info = gather_new_streams(cordelia, cutoff)
        self.assertEqual(stream_count, 0)
        self.assertEqual(stream_info['html'], [])

    def simulate_stream_conversation(self, stream: str, senders: List[str]) -> List[int]:
        client = 'website'  # this makes `sent_by_human` return True
        sending_client = get_client(client)
        message_ids = []  # List[int]
        for sender_name in senders:
            sender = self.example_user(sender_name)
            content = f'some content for {stream} from {sender_name}'
            message_id = self.send_stream_message(sender, stream, content)
            message_ids.append(message_id)
        Message.objects.filter(id__in=message_ids).update(sending_client=sending_client)
        return message_ids

class TestDigestContentInBrowser(ZulipTestCase):
    def test_get_digest_content_in_browser(self) -> None:
        self.login('hamlet')
        result = self.client_get("/digest/")
        self.assert_in_success_response(["Click here to log in to Zulip and catch up."], result)
