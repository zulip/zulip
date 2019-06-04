# -*- coding: utf-8 -*-

import datetime
import mock
import time
from typing import List

from django.test import override_settings
from django.utils.timezone import now as timezone_now

from confirmation.models import one_click_unsubscribe_link
from zerver.lib.actions import create_stream_if_needed, do_create_user
from zerver.lib.digest import gather_new_streams, handle_digest_email, enqueue_emails, \
    exclude_subscription_modified_streams
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import queries_captured
from zerver.models import get_client, get_realm, flush_per_request_caches, \
    Realm, Message, UserActivity, UserProfile, RealmAuditLog, get_stream

class TestDigestEmailMessages(ZulipTestCase):

    @mock.patch('zerver.lib.digest.enough_traffic')
    @mock.patch('zerver.lib.digest.send_future_email')
    def test_multiple_stream_senders(self,
                                     mock_send_future_email: mock.MagicMock,
                                     mock_enough_traffic: mock.MagicMock) -> None:

        othello = self.example_user('othello')
        self.subscribe(othello, 'Verona')

        one_day_ago = timezone_now() - datetime.timedelta(days=1)
        Message.objects.all().update(pub_date=one_day_ago)
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

        self.assert_length(queries, 6)

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
    def test_soft_deactivated_user_multiple_stream_senders(self,
                                                           mock_send_future_email: mock.MagicMock,
                                                           mock_enough_traffic: mock.MagicMock) -> None:

        one_day_ago = timezone_now() - datetime.timedelta(days=1)
        Message.objects.all().update(pub_date=one_day_ago)

        othello = self.example_user('othello')
        for stream in ['Verona', 'Scotland', 'Denmark']:
            self.subscribe(othello, stream)
        RealmAuditLog.objects.all().delete()

        othello.long_term_idle = True
        othello.save(update_fields=['long_term_idle'])

        # Send messages to a stream and unsubscribe - subscribe from that stream
        senders = ['hamlet', 'cordelia',  'iago', 'prospero', 'ZOE']
        self.simulate_stream_conversation('Verona', senders)
        self.unsubscribe(othello, 'Verona')
        self.subscribe(othello, 'Verona')

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
        one_click_unsubscribe_link(othello, 'digest')
        with queries_captured() as queries:
            handle_digest_email(othello.id, cutoff)

        # This can definitely be optimized; for both the huddle and
        # stream cases, the get_narrow_url API ends up double-fetching
        # some data because of how the functions are organized.
        self.assert_length(queries, 9)

        self.assertEqual(mock_send_future_email.call_count, 1)
        kwargs = mock_send_future_email.call_args[1]
        self.assertEqual(kwargs['to_user_ids'], [othello.id])

        hot_conversations = kwargs['context']['hot_conversations']
        self.assertEqual(2, len(hot_conversations), [othello.id])

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

    def test_exclude_subscription_modified_streams(self) -> None:
        othello = self.example_user('othello')
        for stream in ['Verona', 'Scotland', 'Denmark']:
            self.subscribe(othello, stream)

        # Delete all RealmAuditLogs to ignore any changes to subscriptions to
        # streams done for the setup.
        RealmAuditLog.objects.all().delete()

        realm = othello.realm
        stream_names = self.get_streams(othello.email, realm)
        stream_ids = {name: get_stream(name, realm).id for name in stream_names}

        # Unsubscribe and subscribe from a stream
        self.unsubscribe(othello, 'Verona')
        self.subscribe(othello, 'Verona')

        one_sec_ago = timezone_now() - datetime.timedelta(seconds=1)

        filtered_stream_ids = exclude_subscription_modified_streams(
            othello, list(stream_ids.values()), one_sec_ago)
        self.assertNotIn(stream_ids['Verona'], filtered_stream_ids)
        self.assertIn(stream_ids['Scotland'], filtered_stream_ids)
        self.assertIn(stream_ids['Denmark'], filtered_stream_ids)

    @mock.patch('zerver.lib.digest.queue_digest_recipient')
    @mock.patch('zerver.lib.digest.timezone_now')
    @override_settings(SEND_DIGEST_EMAILS=True)
    def test_inactive_users_queued_for_digest(self, mock_django_timezone: mock.MagicMock,
                                              mock_queue_digest_recipient: mock.MagicMock) -> None:
        # Turn on realm digest emails for all realms
        Realm.objects.update(digest_emails_enabled=True)
        cutoff = timezone_now()
        # Test Tuesday
        mock_django_timezone.return_value = datetime.datetime(year=2016, month=1, day=5)
        all_user_profiles = UserProfile.objects.filter(
            is_active=True, is_bot=False, enable_digest_emails=True)
        # Check that all users without an a UserActivity entry are considered
        # inactive users and get enqueued.
        enqueue_emails(cutoff)
        self.assertEqual(mock_queue_digest_recipient.call_count, all_user_profiles.count())
        mock_queue_digest_recipient.reset_mock()
        for realm in Realm.objects.filter(deactivated=False, digest_emails_enabled=True):
            user_profiles = all_user_profiles.filter(realm=realm)
            for user_profile in user_profiles:
                UserActivity.objects.create(
                    last_visit=cutoff - datetime.timedelta(days=1),
                    user_profile=user_profile,
                    count=0,
                    client=get_client('test_client'))
        # Check that inactive users are enqueued
        enqueue_emails(cutoff)
        self.assertEqual(mock_queue_digest_recipient.call_count, all_user_profiles.count())

    @mock.patch('zerver.lib.digest.queue_digest_recipient')
    @mock.patch('zerver.lib.digest.timezone_now')
    def test_disabled(self, mock_django_timezone: mock.MagicMock,
                      mock_queue_digest_recipient: mock.MagicMock) -> None:
        cutoff = timezone_now()
        # A Tuesday
        mock_django_timezone.return_value = datetime.datetime(year=2016, month=1, day=5)
        enqueue_emails(cutoff)
        mock_queue_digest_recipient.assert_not_called()

    @mock.patch('zerver.lib.digest.enough_traffic', return_value=True)
    @mock.patch('zerver.lib.digest.timezone_now')
    @override_settings(SEND_DIGEST_EMAILS=True)
    def test_active_users_not_enqueued(self, mock_django_timezone: mock.MagicMock,
                                       mock_enough_traffic: mock.MagicMock) -> None:
        # Turn on realm digest emails for all realms
        Realm.objects.update(digest_emails_enabled=True)
        cutoff = timezone_now()
        # A Tuesday
        mock_django_timezone.return_value = datetime.datetime(year=2016, month=1, day=5)
        realms = Realm.objects.filter(deactivated=False, digest_emails_enabled=True)
        for realm in realms:
            user_profiles = UserProfile.objects.filter(realm=realm)
            for counter, user_profile in enumerate(user_profiles, 1):
                UserActivity.objects.create(
                    last_visit=cutoff + datetime.timedelta(days=1),
                    user_profile=user_profile,
                    count=0,
                    client=get_client('test_client'))
        # Check that an active user is not enqueued
        with mock.patch('zerver.lib.digest.queue_digest_recipient') as mock_queue_digest_recipient:
            enqueue_emails(cutoff)
            self.assertEqual(mock_queue_digest_recipient.call_count, 0)

    @mock.patch('zerver.lib.digest.queue_digest_recipient')
    @mock.patch('zerver.lib.digest.timezone_now')
    @override_settings(SEND_DIGEST_EMAILS=True)
    def test_only_enqueue_on_valid_day(self, mock_django_timezone: mock.MagicMock,
                                       mock_queue_digest_recipient: mock.MagicMock) -> None:
        # Not a Tuesday
        mock_django_timezone.return_value = datetime.datetime(year=2016, month=1, day=6)

        # Check that digests are not sent on days other than Tuesday.
        cutoff = timezone_now()
        enqueue_emails(cutoff)
        self.assertEqual(mock_queue_digest_recipient.call_count, 0)

    @mock.patch('zerver.lib.digest.queue_digest_recipient')
    @mock.patch('zerver.lib.digest.timezone_now')
    @override_settings(SEND_DIGEST_EMAILS=True)
    def test_no_email_digest_for_bots(self, mock_django_timezone: mock.MagicMock,
                                      mock_queue_digest_recipient: mock.MagicMock) -> None:
        # Turn on realm digest emails for all realms
        Realm.objects.update(digest_emails_enabled=True)
        cutoff = timezone_now()
        # A Tuesday
        mock_django_timezone.return_value = datetime.datetime(year=2016, month=1, day=5)
        bot = do_create_user('some_bot@example.com', 'password', get_realm('zulip'), 'some_bot', '',
                             bot_type=UserProfile.DEFAULT_BOT)
        UserActivity.objects.create(
            last_visit=cutoff - datetime.timedelta(days=1),
            user_profile=bot,
            count=0,
            client=get_client('test_client'))

        # Check that bots are not sent emails
        enqueue_emails(cutoff)
        for arg in mock_queue_digest_recipient.call_args_list:
            user = arg[0][0]
            self.assertNotEqual(user.id, bot.id)

    @mock.patch('zerver.lib.digest.timezone_now')
    @override_settings(SEND_DIGEST_EMAILS=True)
    def test_new_stream_link(self, mock_django_timezone: mock.MagicMock) -> None:
        cutoff = datetime.datetime(year=2017, month=11, day=1)
        mock_django_timezone.return_value = datetime.datetime(year=2017, month=11, day=5)
        cordelia = self.example_user('cordelia')
        stream_id = create_stream_if_needed(cordelia.realm, 'New stream')[0].id
        new_stream = gather_new_streams(cordelia, cutoff)[1]
        expected_html = "<a href='http://zulip.testserver/#narrow/stream/{stream_id}-New-stream'>New stream</a>".format(stream_id=stream_id)
        self.assertIn(expected_html, new_stream['html'])

    def simulate_stream_conversation(self, stream: str, senders: List[str]) -> List[int]:
        client = 'website'  # this makes `sent_by_human` return True
        sending_client = get_client(client)
        message_ids = []  # List[int]
        for sender_name in senders:
            email = self.example_email(sender_name)
            content = 'some content for {} from {}'.format(stream, email)
            message_id = self.send_stream_message(email, stream, content)
            message_ids.append(message_id)
        Message.objects.filter(id__in=message_ids).update(sending_client=sending_client)
        return message_ids

class TestDigestContentInBrowser(ZulipTestCase):
    def test_get_digest_content_in_browser(self) -> None:
        self.login(self.example_email('hamlet'))
        result = self.client_get("/digest/")
        self.assert_in_success_response(["Click here to log in to Zulip and catch up."], result)
