import time
from datetime import datetime, timedelta, timezone
from typing import List, Set
from unittest import mock

import time_machine
from django.test import override_settings
from django.utils.timezone import now as timezone_now

from confirmation.models import one_click_unsubscribe_link
from zerver.actions.create_user import do_create_user
from zerver.actions.realm_settings import do_set_realm_property
from zerver.actions.users import do_deactivate_user
from zerver.lib.digest import (
    DigestTopic,
    _enqueue_emails_for_realm,
    bulk_handle_digest_email,
    bulk_write_realm_audit_logs,
    enqueue_emails,
    gather_new_streams,
    get_hot_topics,
    get_recent_topics,
    get_recently_created_streams,
    get_user_stream_map,
)
from zerver.lib.message import get_last_message_id
from zerver.lib.streams import create_stream_if_needed
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message, Realm, RealmAuditLog, Stream, UserActivityInterval, UserProfile
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream


class TestDigestEmailMessages(ZulipTestCase):
    @mock.patch("zerver.lib.digest.enough_traffic")
    @mock.patch("zerver.lib.digest.send_future_email")
    def test_multiple_stream_senders(
        self, mock_send_future_email: mock.MagicMock, mock_enough_traffic: mock.MagicMock
    ) -> None:
        othello = self.example_user("othello")
        self.subscribe(othello, "Verona")

        one_day_ago = timezone_now() - timedelta(days=1)
        Message.objects.all().update(date_sent=one_day_ago)
        one_hour_ago = timezone_now() - timedelta(seconds=3600)

        cutoff = time.mktime(one_hour_ago.timetuple())

        senders = ["hamlet", "cordelia", "iago", "prospero", "ZOE"]
        self.simulate_stream_conversation("Verona", senders)

        # Remove RealmAuditLog rows, so we don't exclude polonius.
        RealmAuditLog.objects.all().delete()

        # When this test is run in isolation, one additional query is run which
        # is equivalent to
        # ContentType.objects.get(app_label='zerver', model='userprofile')
        # This code is run when we call `confirmation.models.create_confirmation_link`.
        # To trigger this, we call the one_click_unsubscribe_link function below.
        one_click_unsubscribe_link(othello, "digest")

        # Clear the LRU cache on the stream topics
        get_recent_topics.cache_clear()
        with self.assert_database_query_count(10):
            bulk_handle_digest_email([othello.id], cutoff)

        self.assertEqual(mock_send_future_email.call_count, 1)
        kwargs = mock_send_future_email.call_args[1]
        self.assertEqual(kwargs["to_user_ids"], [othello.id])

        hot_convo = kwargs["context"]["hot_conversations"][0]

        expected_participants = {self.example_user(sender).full_name for sender in senders}

        self.assertEqual(set(hot_convo["participants"]), expected_participants)
        self.assertEqual(hot_convo["count"], 5 - 2)  # 5 messages, but 2 shown
        teaser_messages = hot_convo["first_few_messages"][0]["senders"]
        self.assertIn("some content", teaser_messages[0]["content"][0]["plain"])
        self.assertIn(teaser_messages[0]["sender"], expected_participants)

        # If we run another batch, we reuse the topic queries; there
        # are 3 reused streams and one new one, for a net of two fewer
        # than before.
        iago = self.example_user("iago")
        with self.assert_database_query_count(8):
            bulk_handle_digest_email([iago.id], cutoff)
        self.assertEqual(get_recent_topics.cache_info().hits, 3)
        self.assertEqual(get_recent_topics.cache_info().currsize, 4)

        # Two users in the same batch, with only one new stream from
        # the above.
        cordelia = self.example_user("cordelia")
        prospero = self.example_user("prospero")
        with self.assert_database_query_count(9):
            bulk_handle_digest_email([cordelia.id, prospero.id], cutoff)
        self.assertEqual(get_recent_topics.cache_info().hits, 7)
        self.assertEqual(get_recent_topics.cache_info().currsize, 5)

        # If we use a different cutoff, it clears the cache.
        with self.assert_database_query_count(12):
            bulk_handle_digest_email([cordelia.id, prospero.id], cutoff + 1)
        self.assertEqual(get_recent_topics.cache_info().hits, 1)
        self.assertEqual(get_recent_topics.cache_info().currsize, 4)

    def test_bulk_handle_digest_email_skips_deactivated_users(self) -> None:
        """
        A user id may be added to the queue before the user is deactivated. In such a case,
        the function responsible for sending the email should correctly skip them.
        """
        realm = get_realm("zulip")
        hamlet = self.example_user("hamlet")
        user_ids = list(
            UserProfile.objects.filter(is_bot=False, realm=realm).values_list("id", flat=True)
        )

        do_deactivate_user(hamlet, acting_user=None)

        with mock.patch("zerver.lib.digest.enough_traffic", return_value=True), mock.patch(
            "zerver.lib.digest.send_future_email"
        ) as mock_send_email:
            bulk_handle_digest_email(user_ids, 1)

        emailed_user_ids = [
            call_args[1]["to_user_ids"][0] for call_args in mock_send_email.call_args_list
        ]

        self.assertEqual(
            set(emailed_user_ids), {user_id for user_id in user_ids if user_id != hamlet.id}
        )

    @mock.patch("zerver.lib.digest.send_future_email")
    def test_enough_traffic(self, mock_send_future_email: mock.MagicMock) -> None:
        othello = self.example_user("othello")
        self.subscribe(othello, "Verona")

        in_the_future = timezone_now().timestamp() + 60

        bulk_handle_digest_email([othello.id], in_the_future)
        mock_send_future_email.assert_not_called()

        with mock.patch(
            "zerver.lib.digest.enough_traffic", return_value=True
        ) as enough_traffic_mock:
            bulk_handle_digest_email([othello.id], in_the_future)
            mock_send_future_email.assert_called()
            enough_traffic_mock.assert_called_once_with([], 0)

    @mock.patch("zerver.lib.digest.enough_traffic")
    @mock.patch("zerver.lib.digest.send_future_email")
    def test_guest_user_multiple_stream_sender(
        self, mock_send_future_email: mock.MagicMock, mock_enough_traffic: mock.MagicMock
    ) -> None:
        othello = self.example_user("othello")
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        polonius = self.example_user("polonius")
        create_stream_if_needed(cordelia.realm, "web_public_stream", is_web_public=True)
        self.subscribe(othello, "web_public_stream")
        self.subscribe(hamlet, "web_public_stream")
        self.subscribe(cordelia, "web_public_stream")
        self.subscribe(polonius, "web_public_stream")

        one_day_ago = timezone_now() - timedelta(days=1)
        Message.objects.all().update(date_sent=one_day_ago)
        one_hour_ago = timezone_now() - timedelta(seconds=3600)

        cutoff = time.mktime(one_hour_ago.timetuple())

        senders = ["hamlet", "cordelia", "othello", "desdemona"]
        self.simulate_stream_conversation("web_public_stream", senders)

        # Remove RealmAuditoLog rows, so we don't exclude polonius.
        RealmAuditLog.objects.all().delete()

        # When this test is run in isolation, one additional query is run which
        # is equivalent to
        # ContentType.objects.get(app_label='zerver', model='userprofile')
        # This code is run when we call `confirmation.models.create_confirmation_link`.
        # To trigger this, we call the one_click_unsubscribe_link function below.
        one_click_unsubscribe_link(polonius, "digest")
        get_recent_topics.cache_clear()
        with self.assert_database_query_count(9):
            bulk_handle_digest_email([polonius.id], cutoff)

        self.assertEqual(mock_send_future_email.call_count, 1)
        kwargs = mock_send_future_email.call_args[1]
        self.assertEqual(kwargs["to_user_ids"], [polonius.id])

        new_stream_names = kwargs["context"]["new_channels"]["plain"]
        self.assertTrue("web_public_stream" in new_stream_names)

    def test_no_logging(self) -> None:
        hamlet = self.example_user("hamlet")
        startlen = len(RealmAuditLog.objects.all())
        bulk_write_realm_audit_logs([])
        self.assert_length(RealmAuditLog.objects.all(), startlen)
        bulk_write_realm_audit_logs([hamlet])
        self.assert_length(RealmAuditLog.objects.all(), startlen + 1)

    def test_soft_deactivated_user_multiple_stream_senders(self) -> None:
        one_day_ago = timezone_now() - timedelta(days=1)
        Message.objects.all().update(date_sent=one_day_ago)

        digest_users = [
            self.example_user("othello"),
            self.example_user("aaron"),
            self.example_user("desdemona"),
            self.example_user("polonius"),
        ]
        digest_users.sort(key=lambda user: user.id)

        for digest_user in digest_users:
            for stream in ["Verona", "Scotland", "Denmark"]:
                self.subscribe(digest_user, stream)

        RealmAuditLog.objects.all().delete()

        # Send messages to a stream and unsubscribe - subscribe from that stream
        senders = ["hamlet", "cordelia", "iago", "prospero", "ZOE"]
        self.simulate_stream_conversation("Verona", senders)

        for digest_user in digest_users:
            self.unsubscribe(digest_user, "Verona")
            self.subscribe(digest_user, "Verona")

        # Send messages to other streams
        self.simulate_stream_conversation("Scotland", senders)
        self.simulate_stream_conversation("Denmark", senders)

        one_hour_ago = timezone_now() - timedelta(seconds=3600)
        cutoff = time.mktime(one_hour_ago.timetuple())

        # When this test is run in isolation, one additional query is run which
        # is equivalent to
        # ContentType.objects.get(app_label='zerver', model='userprofile')
        # This code is run when we call `confirmation.models.create_confirmation_link`.
        # To trigger this, we call the one_click_unsubscribe_link function below.
        one_click_unsubscribe_link(digest_users[0], "digest")

        with mock.patch("zerver.lib.digest.send_future_email") as mock_send_future_email:
            digest_user_ids = [user.id for user in digest_users]

            get_recent_topics.cache_clear()
            with self.assert_database_query_count(14):
                with self.assert_memcached_count(0):
                    bulk_handle_digest_email(digest_user_ids, cutoff)

        self.assert_length(digest_users, mock_send_future_email.call_count)

        for i, digest_user in enumerate(digest_users):
            kwargs = mock_send_future_email.call_args_list[i][1]
            self.assertEqual(kwargs["to_user_ids"], [digest_user.id])

            hot_conversations = kwargs["context"]["hot_conversations"]
            self.assertEqual(2, len(hot_conversations), [digest_user.id])

            hot_convo = hot_conversations[0]
            expected_participants = {self.example_user(sender).full_name for sender in senders}

            self.assertEqual(set(hot_convo["participants"]), expected_participants)
            self.assertEqual(hot_convo["count"], 5 - 2)  # 5 messages, but 2 shown
            teaser_messages = hot_convo["first_few_messages"][0]["senders"]
            self.assertIn("some content", teaser_messages[0]["content"][0]["plain"])
            self.assertIn(teaser_messages[0]["sender"], expected_participants)

        last_message_id = get_last_message_id()
        for digest_user in digest_users:
            log_rows = RealmAuditLog.objects.filter(
                modified_user_id=digest_user.id,
                event_type=RealmAuditLog.USER_DIGEST_EMAIL_CREATED,
            )
            (log,) = log_rows
            self.assertEqual(log.event_last_message_id, last_message_id)

    def test_streams_recently_modified_for_user(self) -> None:
        othello = self.example_user("othello")
        cordelia = self.example_user("cordelia")

        for stream in ["Verona", "Scotland", "Denmark"]:
            self.subscribe(othello, stream)
            self.subscribe(cordelia, stream)

        realm = othello.realm
        verona = get_stream("Verona", realm)
        scotland = get_stream("Scotland", realm)
        denmark = get_stream("Denmark", realm)

        def user_streams(user: UserProfile) -> Set[Stream]:
            data = get_user_stream_map([user.id], one_hour_ago)
            return {Stream.objects.get(id=stream_id) for stream_id in data[user.id]}

        two_hours_ago = timezone_now() - timedelta(hours=2)
        one_hour_ago = timezone_now() - timedelta(hours=1)

        # Delete all RealmAuditLogs to start with a clean slate.
        RealmAuditLog.objects.all().delete()

        # Othello's map is Verona, Scotland, and Denmark
        self.assertEqual(user_streams(othello), {verona, scotland, denmark})

        # Unsubscribe and subscribe Othello from a stream
        self.unsubscribe(othello, "Denmark")
        self.subscribe(othello, "Denmark")

        # This drops denmark from the list of streams
        self.assertEqual(user_streams(othello), {verona, scotland})

        # Backdate all our logs (so that Denmark will no longer
        # appear like a recently modified stream for Othello).
        RealmAuditLog.objects.all().update(event_time=two_hours_ago)

        # Now Denmark no longer appears recent to Othello.
        self.assertEqual(user_streams(othello), {denmark, verona, scotland})

        # Unsubscribe and subscribe from a stream
        self.unsubscribe(othello, "Verona")
        self.subscribe(othello, "Verona")

        # Now, Verona, but not Denmark, appears recent.
        self.assertEqual(user_streams(othello), {denmark, scotland})

        # make sure we don't mix up Othello and Cordelia
        streams = get_user_stream_map([othello.id, cordelia.id], one_hour_ago)
        self.assertEqual(streams[othello.id], {scotland.id, denmark.id})
        self.assertEqual(streams[cordelia.id], {verona.id, scotland.id, denmark.id})

        self.unsubscribe(cordelia, "Denmark")
        self.subscribe(cordelia, "Denmark")

        streams = get_user_stream_map([othello.id, cordelia.id], one_hour_ago)
        self.assertEqual(streams[othello.id], {scotland.id, denmark.id})
        self.assertEqual(streams[cordelia.id], {verona.id, scotland.id})

    def active_human_users(self, realm: Realm) -> List[UserProfile]:
        users = list(
            UserProfile.objects.filter(
                realm=realm,
                is_active=True,
                is_bot=False,
                enable_digest_emails=True,
            )
        )

        assert len(users) >= 5

        return users

    def test_twelve_hour_exemption(self) -> None:
        RealmAuditLog.objects.all().delete()

        realm = get_realm("zulip")

        cutoff = timezone_now() - timedelta(days=5)

        with mock.patch("zerver.lib.digest.queue_digest_user_ids") as queue_mock:
            _enqueue_emails_for_realm(realm, cutoff)

        users = self.active_human_users(realm)

        num_queued_users = len(queue_mock.call_args[0][0])
        self.assert_length(users, num_queued_users)

        # Simulate that we have sent digests for all our users.
        bulk_write_realm_audit_logs(users)

        # Now if we run again, we won't get any users, since they will have
        # recent RealmAuditLog rows.
        with mock.patch("zerver.lib.digest.queue_digest_user_ids") as queue_mock:
            _enqueue_emails_for_realm(realm, cutoff)

        self.assertEqual(queue_mock.call_count, 0)

    @override_settings(SEND_DIGEST_EMAILS=True)
    @override_settings(SYSTEM_ONLY_REALMS=["zulipinternal"])
    def test_enqueue_emails(self) -> None:
        def call_enqueue_emails(realm: Realm) -> int:
            do_set_realm_property(realm, "digest_emails_enabled", True, acting_user=None)
            do_set_realm_property(
                realm, "digest_weekday", timezone_now().weekday(), acting_user=None
            )
            cutoff = timezone_now() - timedelta(days=0)
            with mock.patch("zerver.worker.digest_emails.bulk_handle_digest_email") as queue_mock:
                enqueue_emails(cutoff)
            return 0 if queue_mock.call_args is None else len(queue_mock.call_args[0][0])

        num_queued_users = call_enqueue_emails(get_realm("zulipinternal"))
        self.assertEqual(num_queued_users, 0)
        num_queued_users = call_enqueue_emails(get_realm("zulip"))
        self.assertEqual(num_queued_users, 10)

    @override_settings(SEND_DIGEST_EMAILS=True)
    def test_inactive_users_queued_for_digest(self) -> None:
        UserActivityInterval.objects.all().delete()
        RealmAuditLog.objects.all().delete()
        # Turn on realm digest emails for all realms
        Realm.objects.update(digest_emails_enabled=True)
        cutoff = timezone_now() - timedelta(days=5)

        realm = get_realm("zulip")
        users = self.active_human_users(realm)

        # Check that all users without a UserActivityInterval entry are considered
        # inactive users and get enqueued.
        with mock.patch("zerver.worker.digest_emails.bulk_handle_digest_email") as queue_mock:
            _enqueue_emails_for_realm(realm, cutoff)

        num_queued_users = len(queue_mock.call_args[0][0])
        self.assert_length(users, num_queued_users)

        for user in users:
            last_visit = timezone_now() - timedelta(days=1)
            UserActivityInterval.objects.create(
                start=last_visit,
                end=last_visit,
                user_profile=user,
            )

        # Now we expect no users, due to recent activity.
        with mock.patch("zerver.worker.digest_emails.bulk_handle_digest_email") as queue_mock:
            _enqueue_emails_for_realm(realm, cutoff)

        self.assertEqual(queue_mock.call_count, 0)

        # Now, backdate all our users activity.
        last_visit = timezone_now() - timedelta(days=7)
        UserActivityInterval.objects.all().update(start=last_visit, end=last_visit)

        with mock.patch("zerver.worker.digest_emails.bulk_handle_digest_email") as queue_mock:
            _enqueue_emails_for_realm(realm, cutoff)

        num_queued_users = len(queue_mock.call_args[0][0])
        self.assert_length(users, num_queued_users)

    def tuesday(self) -> datetime:
        return datetime(year=2016, month=1, day=5, tzinfo=timezone.utc)

    @override_settings(SEND_DIGEST_EMAILS=False)
    def test_disabled(self) -> None:
        RealmAuditLog.objects.all().delete()

        tuesday = self.tuesday()
        cutoff = tuesday - timedelta(days=5)

        with time_machine.travel(tuesday, tick=False):
            with mock.patch("zerver.lib.digest.queue_digest_user_ids") as queue_mock:
                enqueue_emails(cutoff)
        queue_mock.assert_not_called()

    @override_settings(SEND_DIGEST_EMAILS=True)
    def test_only_enqueue_on_valid_day(self) -> None:
        RealmAuditLog.objects.all().delete()

        not_tuesday = datetime(year=2016, month=1, day=6, tzinfo=timezone.utc)
        cutoff = not_tuesday - timedelta(days=5)

        with time_machine.travel(not_tuesday, tick=False):
            with mock.patch("zerver.lib.digest.queue_digest_user_ids") as queue_mock:
                enqueue_emails(cutoff)
        queue_mock.assert_not_called()

    @override_settings(SEND_DIGEST_EMAILS=True)
    def test_no_email_digest_for_bots(self) -> None:
        RealmAuditLog.objects.all().delete()

        cutoff = timezone_now() - timedelta(days=5)

        realm = get_realm("zulip")
        realm.digest_emails_enabled = True
        realm.save()

        bot = do_create_user(
            "some_bot@example.com",
            "password",
            realm,
            "some_bot",
            bot_type=UserProfile.DEFAULT_BOT,
            acting_user=None,
        )

        # Check that bots are not sent emails
        with mock.patch("zerver.lib.digest.queue_digest_user_ids") as queue_mock:
            _enqueue_emails_for_realm(realm, cutoff)

        num_queued_users = len(queue_mock.call_args[0][0])
        assert num_queued_users >= 5

        for arg in queue_mock.call_args_list:
            user_ids = arg[0][0]
            for user_id in user_ids:
                self.assertNotEqual(user_id, bot.id)

    @override_settings(SEND_DIGEST_EMAILS=True)
    def test_new_stream_link(self) -> None:
        Stream.objects.all().delete()
        cutoff = timezone_now() - timedelta(days=5)
        cordelia = self.example_user("cordelia")
        stream = create_stream_if_needed(cordelia.realm, "New stream")[0]
        stream.date_created = timezone_now()
        stream.save()

        realm = cordelia.realm

        recently_created_streams = get_recently_created_streams(realm, cutoff)
        stream_count, stream_info = gather_new_streams(
            realm, recently_created_streams, can_access_public=True
        )
        self.assertEqual(stream_count, 1)
        expected_html = f"<a href='http://zulip.testserver/#narrow/stream/{stream.id}-New-stream'>New stream</a>"
        self.assertEqual(stream_info["html"][0], expected_html)

        # guests don't see our stream
        stream_count, stream_info = gather_new_streams(
            realm, recently_created_streams, can_access_public=False
        )
        self.assertEqual(stream_count, 0)
        self.assertEqual(stream_info["html"], [])

        # but they do if we make it web-public
        stream.is_web_public = True
        stream.save()

        recently_created_streams = get_recently_created_streams(realm, cutoff)
        stream_count, stream_info = gather_new_streams(
            realm, recently_created_streams, can_access_public=True
        )
        self.assertEqual(stream_count, 1)

        # Make the stream appear to be older.
        stream.date_created = timezone_now() - timedelta(days=7)
        stream.save()

        recently_created_streams = get_recently_created_streams(realm, cutoff)
        stream_count, stream_info = gather_new_streams(
            realm, recently_created_streams, can_access_public=True
        )
        self.assertEqual(stream_count, 0)
        self.assertEqual(stream_info["html"], [])

    def simulate_stream_conversation(self, stream: str, senders: List[str]) -> List[int]:
        message_ids = []  # List[int]
        for sender_name in senders:
            sender = self.example_user(sender_name)
            self.subscribe(sender, stream)
            content = f"some content for {stream} from {sender_name}"
            message_id = self.send_stream_message(sender, stream, content)
            message_ids.append(message_id)
        return message_ids


class TestDigestContentInBrowser(ZulipTestCase):
    def test_get_digest_content_in_browser(self) -> None:
        self.login("hamlet")
        result = self.client_get("/digest/")
        self.assert_in_success_response(["Click here to log in to Zulip and catch up."], result)


class TestDigestTopics(ZulipTestCase):
    def populate_topic(
        self,
        topic: DigestTopic,
        humans: int,
        human_messages: int,
        bots: int,
        bot_messages: int,
        realm: Realm,
    ) -> None:
        for is_bot, users, messages in [
            (False, humans, human_messages),
            (True, bots, bot_messages),
        ]:
            messages_sent = 0
            while messages_sent < messages:
                for index, username in enumerate(self.example_user_map, start=1):
                    if self.example_user(username).is_bot != is_bot:
                        continue
                    topic.add_message(Message(sender=self.example_user(username), realm=realm))
                    messages_sent += 1
                    if messages_sent == messages:
                        break
                    if index == users:
                        break

    def test_get_hot_topics(self) -> None:
        realm = get_realm("zulip")
        denmark = get_stream("Denmark", realm)
        verona = get_stream("Verona", realm)
        diverse_topic_a = DigestTopic((denmark.id, "5 humans talking"))
        self.populate_topic(
            diverse_topic_a, humans=5, human_messages=10, bots=0, bot_messages=0, realm=realm
        )

        diverse_topic_b = DigestTopic((denmark.id, "4 humans talking"))
        self.populate_topic(
            diverse_topic_b, humans=4, human_messages=15, bots=0, bot_messages=0, realm=realm
        )

        diverse_topic_c = DigestTopic((verona.id, "5 humans talking in another stream"))
        self.populate_topic(
            diverse_topic_c, humans=5, human_messages=15, bots=0, bot_messages=0, realm=realm
        )

        diverse_topic_d = DigestTopic((denmark.id, "3 humans and 2 bots talking"))
        self.populate_topic(
            diverse_topic_d, humans=3, human_messages=15, bots=2, bot_messages=10, realm=realm
        )

        diverse_topic_e = DigestTopic((denmark.id, "3 humans talking"))
        self.populate_topic(
            diverse_topic_a, humans=3, human_messages=20, bots=0, bot_messages=0, realm=realm
        )

        lengthy_topic_a = DigestTopic((denmark.id, "2 humans talking a lot"))
        self.populate_topic(
            lengthy_topic_a, humans=2, human_messages=40, bots=0, bot_messages=0, realm=realm
        )

        lengthy_topic_b = DigestTopic((denmark.id, "2 humans talking"))
        self.populate_topic(
            lengthy_topic_b, humans=2, human_messages=30, bots=0, bot_messages=0, realm=realm
        )

        lengthy_topic_c = DigestTopic((denmark.id, "a human and bot talking"))
        self.populate_topic(
            lengthy_topic_c, humans=1, human_messages=20, bots=1, bot_messages=20, realm=realm
        )

        lengthy_topic_d = DigestTopic((verona.id, "2 humans talking in another stream"))
        self.populate_topic(
            lengthy_topic_d, humans=2, human_messages=35, bots=0, bot_messages=0, realm=realm
        )

        topics = [
            diverse_topic_a,
            diverse_topic_b,
            diverse_topic_c,
            diverse_topic_d,
            diverse_topic_e,
            lengthy_topic_a,
            lengthy_topic_b,
            lengthy_topic_c,
            lengthy_topic_d,
        ]
        self.assertEqual(
            get_hot_topics(topics, {denmark.id, 0}),
            [diverse_topic_a, diverse_topic_b, lengthy_topic_a, lengthy_topic_b],
        )
        self.assertEqual(
            get_hot_topics(topics, {denmark.id, verona.id}),
            [diverse_topic_a, diverse_topic_c, lengthy_topic_a, lengthy_topic_d],
        )
        self.assertEqual(get_hot_topics(topics, {verona.id}), [diverse_topic_c, lengthy_topic_d])
        self.assertEqual(get_hot_topics(topics, set()), [])
