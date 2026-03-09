from datetime import timedelta

from django.utils.timezone import now as timezone_now

from zerver.lib.catch_up import (
    CatchUpTopic,
    annotate_mention_flags,
    annotate_reaction_counts,
    get_catch_up_messages,
    get_last_active_time,
    get_subscribed_stream_map,
    rank_topics,
)
from zerver.lib.catch_up_summarizer import (
    ScoredMessage,
    extract_key_messages,
    extract_keywords,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import (
    Message,
    Reaction,
    Recipient,
    UserMessage,
    UserProfile,
)
from zerver.models.presence import UserPresence
from zerver.models.user_activity import UserActivityInterval


class GetLastActiveTimeTest(ZulipTestCase):
    def test_last_active_time_from_presence(self) -> None:
        """When UserPresence has a last_active_time, it should be returned."""
        hamlet = self.example_user("hamlet")
        expected_time = timezone_now() - timedelta(hours=6)

        # Ensure a presence row exists.
        UserPresence.objects.update_or_create(
            user_profile=hamlet,
            defaults={
                "last_active_time": expected_time,
                "realm": hamlet.realm,
            },
        )

        result = get_last_active_time(hamlet)
        self.assertEqual(result, expected_time)

    def test_last_active_time_fallback_to_activity_interval(self) -> None:
        """When UserPresence has no last_active_time, fall back to
        the most recent UserActivityInterval."""
        hamlet = self.example_user("hamlet")

        # Remove any presence data.
        UserPresence.objects.filter(user_profile=hamlet).delete()

        # Create an activity interval.
        interval_end = timezone_now() - timedelta(hours=3)
        UserActivityInterval.objects.create(
            user_profile=hamlet,
            start=interval_end - timedelta(minutes=15),
            end=interval_end,
        )

        result = get_last_active_time(hamlet)
        self.assertEqual(result, interval_end)

    def test_last_active_time_default_when_no_data(self) -> None:
        """When there is no presence or activity data, return a default
        time in the past."""
        hamlet = self.example_user("hamlet")

        # Remove all presence and activity data.
        UserPresence.objects.filter(user_profile=hamlet).delete()
        UserActivityInterval.objects.filter(user_profile=hamlet).delete()

        result = get_last_active_time(hamlet)
        now = timezone_now()
        # Should be approximately 4 hours ago (DEFAULT_INACTIVITY_THRESHOLD_HOURS).
        self.assertAlmostEqual(
            (now - result).total_seconds(),
            4 * 3600,
            delta=60,  # Allow 60 seconds of tolerance.
        )


class GetSubscribedStreamMapTest(ZulipTestCase):
    def test_returns_subscribed_streams(self) -> None:
        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "Verona")
        self.subscribe(hamlet, "Denmark")

        stream_map = get_subscribed_stream_map(hamlet)

        # hamlet should be subscribed to at least Verona and Denmark.
        stream_names = set(stream_map.values())
        self.assertIn("Verona", stream_names)
        self.assertIn("Denmark", stream_names)

    def test_excludes_muted_streams_by_default(self) -> None:
        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "Verona")

        # Mute the Verona stream.
        from zerver.models import Recipient, Subscription

        sub = Subscription.objects.get(
            user_profile=hamlet,
            recipient__type=Recipient.STREAM,
            recipient__type_id__in=hamlet.realm.stream_set.filter(name="Verona").values("id"),
        )
        sub.is_muted = True
        sub.save()

        stream_map = get_subscribed_stream_map(hamlet, include_muted=False)
        self.assertNotIn("Verona", stream_map.values())

    def test_includes_muted_when_requested(self) -> None:
        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "Verona")

        # Mute the Verona stream.
        from zerver.models import Recipient, Subscription

        sub = Subscription.objects.get(
            user_profile=hamlet,
            recipient__type=Recipient.STREAM,
            recipient__type_id__in=hamlet.realm.stream_set.filter(name="Verona").values("id"),
        )
        sub.is_muted = True
        sub.save()

        stream_map = get_subscribed_stream_map(hamlet, include_muted=True)
        self.assertIn("Verona", stream_map.values())


class GetCatchUpMessagesTest(ZulipTestCase):
    def test_aggregates_messages_by_topic(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.subscribe(hamlet, "Verona")
        self.subscribe(cordelia, "Verona")

        since = timezone_now() - timedelta(hours=1)

        # Send messages to different topics.
        self.send_stream_message(cordelia, "Verona", "msg1", topic_name="topic A")
        self.send_stream_message(cordelia, "Verona", "msg2", topic_name="topic A")
        self.send_stream_message(cordelia, "Verona", "msg3", topic_name="topic B")

        stream_map = get_subscribed_stream_map(hamlet)
        topics = get_catch_up_messages(hamlet, since, stream_map)

        # Should have 2 topics.
        topic_names = {key[1] for key in topics}
        self.assertIn("topic A", topic_names)
        self.assertIn("topic B", topic_names)

        # topic A should have 2 messages.
        topic_a = [t for t in topics.values() if t.topic_name == "topic A"][0]
        self.assertEqual(topic_a.message_count, 2)

        # topic B should have 1 message.
        topic_b = [t for t in topics.values() if t.topic_name == "topic B"][0]
        self.assertEqual(topic_b.message_count, 1)

    def test_respects_time_range(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.subscribe(hamlet, "Verona")
        self.subscribe(cordelia, "Verona")

        # Send a message, then set 'since' to after it.
        self.send_stream_message(cordelia, "Verona", "old msg", topic_name="old topic")

        # Move the message to the past.
        Message.objects.filter(content="old msg").update(
            date_sent=timezone_now() - timedelta(hours=5)
        )

        since = timezone_now() - timedelta(hours=1)

        # Send a recent message.
        self.send_stream_message(cordelia, "Verona", "new msg", topic_name="new topic")

        stream_map = get_subscribed_stream_map(hamlet)
        topics = get_catch_up_messages(hamlet, since, stream_map)

        topic_names = {key[1] for key in topics}
        self.assertIn("new topic", topic_names)
        self.assertNotIn("old topic", topic_names)

    def test_only_subscribed_streams(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.subscribe(hamlet, "Verona")
        self.subscribe(cordelia, "Verona")
        self.subscribe(cordelia, "Denmark")

        since = timezone_now() - timedelta(hours=1)

        self.send_stream_message(cordelia, "Verona", "verona msg", topic_name="test")
        self.send_stream_message(cordelia, "Denmark", "denmark msg", topic_name="test")

        stream_map = get_subscribed_stream_map(hamlet)
        topics = get_catch_up_messages(hamlet, since, stream_map)

        # hamlet is only subscribed to Verona, not Denmark (unless
        # the test setup already subscribes them). We check that
        # the returned topics only include streams in stream_map.
        for topic in topics.values():
            self.assertIn(topic.stream_id, stream_map)

    def test_tracks_senders(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        self.subscribe(hamlet, "Verona")
        self.subscribe(cordelia, "Verona")
        self.subscribe(othello, "Verona")

        since = timezone_now() - timedelta(hours=1)

        self.send_stream_message(cordelia, "Verona", "msg from cordelia", topic_name="test")
        self.send_stream_message(othello, "Verona", "msg from othello", topic_name="test")

        stream_map = get_subscribed_stream_map(hamlet)
        topics = get_catch_up_messages(hamlet, since, stream_map)

        topic = [t for t in topics.values() if t.topic_name == "test"][0]
        self.assertEqual(topic.sender_count, 2)
        self.assertIn(cordelia.full_name, topic.senders)
        self.assertIn(othello.full_name, topic.senders)


class ImportanceScoringTest(ZulipTestCase):
    def test_mentions_score_highest(self) -> None:
        """Topics with @-mentions should score higher than those without."""
        now = timezone_now()

        topic_with_mention = CatchUpTopic(
            stream_id=1,
            stream_name="test",
            topic_name="mentioned",
            message_count=3,
            has_mention=True,
        )
        topic_with_mention.human_senders = {"Alice", "Bob"}

        topic_without_mention = CatchUpTopic(
            stream_id=1,
            stream_name="test",
            topic_name="not mentioned",
            message_count=3,
        )
        topic_without_mention.human_senders = {"Alice", "Bob"}

        self.assertGreater(topic_with_mention.score(now), topic_without_mention.score(now))

    def test_more_senders_increases_score(self) -> None:
        """Topics with more unique senders should score higher."""
        now = timezone_now()

        topic_many_senders = CatchUpTopic(
            stream_id=1,
            stream_name="test",
            topic_name="popular",
            message_count=5,
        )
        topic_many_senders.human_senders = {"Alice", "Bob", "Charlie", "Diana"}

        topic_few_senders = CatchUpTopic(
            stream_id=1,
            stream_name="test",
            topic_name="quiet",
            message_count=5,
        )
        topic_few_senders.human_senders = {"Alice"}

        self.assertGreater(topic_many_senders.score(now), topic_few_senders.score(now))

    def test_reactions_increase_score(self) -> None:
        """Topics with more reactions should score higher."""
        now = timezone_now()

        topic_with_reactions = CatchUpTopic(
            stream_id=1,
            stream_name="test",
            topic_name="reacted",
            message_count=3,
            reaction_count=10,
        )
        topic_with_reactions.human_senders = {"Alice"}

        topic_without_reactions = CatchUpTopic(
            stream_id=1,
            stream_name="test",
            topic_name="no reactions",
            message_count=3,
            reaction_count=0,
        )
        topic_without_reactions.human_senders = {"Alice"}

        self.assertGreater(topic_with_reactions.score(now), topic_without_reactions.score(now))

    def test_rank_topics_returns_top_n(self) -> None:
        """rank_topics should return the top N topics by score."""
        topics = {}
        for i in range(10):
            key = (1, f"topic {i}")
            topic = CatchUpTopic(
                stream_id=1,
                stream_name="test",
                topic_name=f"topic {i}",
                message_count=i + 1,
            )
            topic.human_senders = {f"sender_{j}" for j in range(i + 1)}
            topics[key] = topic

        ranked = rank_topics(topics, max_topics=3)
        self.assertEqual(len(ranked), 3)

        # The topics with the most messages and senders should come first.
        scores = [t.score(timezone_now()) for t in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))


class CatchUpEndpointTest(ZulipTestCase):
    def test_catch_up_endpoint_success(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.subscribe(hamlet, "Verona")
        self.subscribe(cordelia, "Verona")

        # Send some messages.
        self.send_stream_message(cordelia, "Verona", "hello world", topic_name="greetings")
        self.send_stream_message(cordelia, "Verona", "second msg", topic_name="greetings")

        self.login_user(hamlet)
        result = self.client_get("/json/catch-up")
        self.assert_json_success(result)

        data = result.json()
        self.assertIn("topics", data)
        self.assertIn("total_messages", data)
        self.assertIn("total_topics", data)
        self.assertIn("last_active_time", data)
        self.assertIn("catch_up_period_hours", data)

    def test_catch_up_endpoint_with_since_param(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.subscribe(hamlet, "Verona")
        self.subscribe(cordelia, "Verona")

        self.send_stream_message(cordelia, "Verona", "recent msg", topic_name="recent")

        self.login_user(hamlet)
        since = (timezone_now() - timedelta(hours=2)).isoformat()
        result = self.client_get("/json/catch-up", {"since": since})
        self.assert_json_success(result)

        data = result.json()
        self.assertIsInstance(data["topics"], list)

    def test_catch_up_endpoint_invalid_since(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        result = self.client_get("/json/catch-up", {"since": "not-a-date"})
        self.assert_json_error(result, "Invalid 'since' timestamp format. Use ISO 8601.")

    def test_catch_up_endpoint_invalid_max_topics(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        result = self.client_get("/json/catch-up", {"max_topics": "0"})
        self.assert_json_error(result, "'max_topics' must be between 1 and 100.")

        result = self.client_get("/json/catch-up", {"max_topics": "200"})
        self.assert_json_error(result, "'max_topics' must be between 1 and 100.")

    def test_catch_up_endpoint_unauthenticated(self) -> None:
        result = self.client_get("/json/catch-up")
        #self.assert_json_error(result, "Not logged in: API authentication or target user required", 401)
        self.assert_json_error(result, "Not logged in: API authentication or user session required", 401)

    def test_catch_up_endpoint_no_messages(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        # Use a 'since' in the future so no messages match.
        since = (timezone_now() + timedelta(hours=1)).isoformat()
        result = self.client_get("/json/catch-up", {"since": since})
        self.assert_json_success(result)

        data = result.json()
        self.assertEqual(data["total_messages"], 0)
        self.assertEqual(data["total_topics"], 0)
        self.assertEqual(data["topics"], [])

    def test_catch_up_endpoint_topics_are_sorted_by_score(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        self.subscribe(hamlet, "Verona")
        self.subscribe(cordelia, "Verona")
        self.subscribe(othello, "Verona")

        since = (timezone_now() - timedelta(hours=1)).isoformat()

        # Create a busy topic (many messages, multiple senders).
        for _ in range(5):
            self.send_stream_message(cordelia, "Verona", "busy", topic_name="busy topic")
        for _ in range(3):
            self.send_stream_message(othello, "Verona", "busy", topic_name="busy topic")

        # Create a quiet topic (one message, one sender).
        self.send_stream_message(cordelia, "Verona", "quiet", topic_name="quiet topic")

        self.login_user(hamlet)
        result = self.client_get("/json/catch-up", {"since": since})
        self.assert_json_success(result)

        data = result.json()
        topics = data["topics"]

        # Find our two topics in the results.
        busy = next((t for t in topics if t["topic_name"] == "busy topic"), None)
        quiet = next((t for t in topics if t["topic_name"] == "quiet topic"), None)

        self.assertIsNotNone(busy)
        self.assertIsNotNone(quiet)

        # The busy topic should have a higher score.
        assert busy is not None
        assert quiet is not None
        self.assertGreater(busy["score"], quiet["score"])

    def test_catch_up_topic_card_data_structure(self) -> None:
        """Verify the data structure of each topic in the response."""
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.subscribe(hamlet, "Verona")
        self.subscribe(cordelia, "Verona")

        since = (timezone_now() - timedelta(hours=1)).isoformat()
        self.send_stream_message(cordelia, "Verona", "test content", topic_name="test topic")

        self.login_user(hamlet)
        result = self.client_get("/json/catch-up", {"since": since})
        self.assert_json_success(result)

        data = result.json()
        # Find the test topic.
        topic = next((t for t in data["topics"] if t["topic_name"] == "test topic"), None)
        self.assertIsNotNone(topic)
        assert topic is not None

        # Verify all expected fields are present.
        expected_fields = {
            "stream_id",
            "stream_name",
            "topic_name",
            "score",
            "message_count",
            "sender_count",
            "senders",
            "has_mention",
            "has_wildcard_mention",
            "has_group_mention",
            "reaction_count",
            "latest_message_id",
            "first_message_id",
            "sample_messages",
        }
        self.assertEqual(set(topic.keys()), expected_fields)

        # Verify types.
        self.assertIsInstance(topic["stream_id"], int)
        self.assertIsInstance(topic["stream_name"], str)
        self.assertIsInstance(topic["score"], (int, float))
        self.assertIsInstance(topic["message_count"], int)
        self.assertIsInstance(topic["senders"], list)
        self.assertIsInstance(topic["sample_messages"], list)

        # Verify sample message structure.
        self.assertGreater(len(topic["sample_messages"]), 0)
        sample = topic["sample_messages"][0]
        self.assertIn("id", sample)
        self.assertIn("sender_full_name", sample)
        self.assertIn("content", sample)
        self.assertIn("date_sent", sample)


class ExtractKeyMessagesTest(ZulipTestCase):
    def test_extracts_messages_from_topic(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.subscribe(hamlet, "Verona")
        self.subscribe(cordelia, "Verona")

        since = timezone_now() - timedelta(hours=1)

        self.send_stream_message(cordelia, "Verona", "first message", topic_name="extract test")
        self.send_stream_message(cordelia, "Verona", "second message", topic_name="extract test")
        self.send_stream_message(cordelia, "Verona", "third message", topic_name="extract test")

        from zerver.models.streams import get_stream

        stream = get_stream("Verona", hamlet.realm)
        key_messages = extract_key_messages(hamlet, stream.id, "extract test", since)

        self.assertGreater(len(key_messages), 0)
        self.assertLessEqual(len(key_messages), 5)

        # Check structure of each key message.
        for msg in key_messages:
            self.assertIn("id", msg)
            self.assertIn("sender_full_name", msg)
            self.assertIn("content", msg)
            self.assertIn("date_sent", msg)
            self.assertIn("tags", msg)
            self.assertIn("reaction_count", msg)

    def test_first_and_last_messages_preferred(self) -> None:
        """First and last messages in a topic should get score bonuses."""
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.subscribe(hamlet, "Verona")
        self.subscribe(cordelia, "Verona")

        since = timezone_now() - timedelta(hours=1)

        # Send several messages; we want to verify first and last
        # appear in key_messages.
        msg_ids = []
        for i in range(8):
            msg_id = self.send_stream_message(
                cordelia, "Verona", f"message {i}", topic_name="position test"
            )
            msg_ids.append(msg_id)

        from zerver.models.streams import get_stream

        stream = get_stream("Verona", hamlet.realm)
        key_messages = extract_key_messages(
            hamlet, stream.id, "position test", since, max_messages=3
        )

        key_ids = [m["id"] for m in key_messages]
        # First message should be included (has IS_FIRST bonus).
        self.assertIn(msg_ids[0], key_ids)
        # Last message should be included (has IS_LAST bonus).
        self.assertIn(msg_ids[-1], key_ids)

    def test_messages_with_reactions_preferred(self) -> None:
        """Messages with more reactions should be preferred."""
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.subscribe(hamlet, "Verona")
        self.subscribe(cordelia, "Verona")

        since = timezone_now() - timedelta(hours=1)

        # Send messages.
        boring_id = self.send_stream_message(
            cordelia, "Verona", "boring message", topic_name="reaction test"
        )
        popular_id = self.send_stream_message(
            cordelia, "Verona", "popular message", topic_name="reaction test"
        )

        # Add reactions to the popular message.
        popular_msg = Message.objects.get(id=popular_id)
        Reaction.objects.create(
            user_profile=hamlet,
            message=popular_msg,
            emoji_name="+1",
            emoji_code="1f44d",
            reaction_type=Reaction.UNICODE_EMOJI,
        )
        Reaction.objects.create(
            user_profile=cordelia,
            message=popular_msg,
            emoji_name="heart",
            emoji_code="2764",
            reaction_type=Reaction.UNICODE_EMOJI,
        )

        from zerver.models.streams import get_stream

        stream = get_stream("Verona", hamlet.realm)
        key_messages = extract_key_messages(
            hamlet, stream.id, "reaction test", since, max_messages=2
        )

        # The popular message should be in the results.
        key_ids = [m["id"] for m in key_messages]
        self.assertIn(popular_id, key_ids)

        # And the one with reactions should have reaction_count > 0.
        popular_entry = next(m for m in key_messages if m["id"] == popular_id)
        self.assertEqual(popular_entry["reaction_count"], 2)

    def test_action_items_tagged(self) -> None:
        """Messages with action item patterns should be tagged."""
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.subscribe(hamlet, "Verona")
        self.subscribe(cordelia, "Verona")

        since = timezone_now() - timedelta(hours=1)

        self.send_stream_message(
            cordelia, "Verona", "TODO: update the deployment docs", topic_name="tag test"
        )
        self.send_stream_message(
            cordelia, "Verona", "just chatting about the weather", topic_name="tag test"
        )

        from zerver.models.streams import get_stream

        stream = get_stream("Verona", hamlet.realm)
        key_messages = extract_key_messages(hamlet, stream.id, "tag test", since)

        todo_msg = next(
            (m for m in key_messages if "TODO" in str(m["content"])),
            None,
        )
        self.assertIsNotNone(todo_msg)
        assert todo_msg is not None
        self.assertIn("action_item", todo_msg["tags"])

    def test_questions_tagged(self) -> None:
        """Messages that are questions should be tagged."""
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.subscribe(hamlet, "Verona")
        self.subscribe(cordelia, "Verona")

        since = timezone_now() - timedelta(hours=1)

        self.send_stream_message(
            cordelia, "Verona", "Does anyone know the deploy process?", topic_name="question test"
        )

        from zerver.models.streams import get_stream

        stream = get_stream("Verona", hamlet.realm)
        key_messages = extract_key_messages(hamlet, stream.id, "question test", since)

        self.assertGreater(len(key_messages), 0)
        self.assertIn("question", key_messages[0]["tags"])

    def test_empty_topic_returns_empty(self) -> None:
        hamlet = self.example_user("hamlet")

        since = timezone_now() - timedelta(hours=1)
        key_messages = extract_key_messages(hamlet, 99999, "nonexistent", since)
        self.assertEqual(key_messages, [])


class ExtractKeywordsTest(ZulipTestCase):
    def test_extracts_frequent_terms(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.subscribe(hamlet, "Verona")
        self.subscribe(cordelia, "Verona")

        self.send_stream_message(
            cordelia, "Verona", "The deployment pipeline needs updating", topic_name="kw test"
        )
        self.send_stream_message(
            cordelia, "Verona", "Yes the deployment is broken in staging", topic_name="kw test"
        )
        self.send_stream_message(
            cordelia, "Verona", "Fixed the deployment issue in production", topic_name="kw test"
        )

        from zerver.models.streams import get_stream

        stream = get_stream("Verona", hamlet.realm)
        recipient = Recipient.objects.get(type=Recipient.STREAM, type_id=stream.id)

        messages = list(
            Message.objects.filter(
                recipient=recipient,
                subject__iexact="kw test",
            ).order_by("id")
        )

        keywords = extract_keywords(messages)
        # "deployment" appears in all 3 messages, so should be first.
        self.assertIn("deployment", keywords)

    def test_excludes_stopwords(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.subscribe(hamlet, "Verona")
        self.subscribe(cordelia, "Verona")

        self.send_stream_message(
            cordelia, "Verona", "the the the and and and", topic_name="stopword test"
        )

        from zerver.models.streams import get_stream

        stream = get_stream("Verona", hamlet.realm)
        recipient = Recipient.objects.get(type=Recipient.STREAM, type_id=stream.id)

        messages = list(
            Message.objects.filter(
                recipient=recipient,
                subject__iexact="stopword test",
            ).order_by("id")
        )

        keywords = extract_keywords(messages)
        # Stopwords should be filtered out.
        self.assertNotIn("the", keywords)
        self.assertNotIn("and", keywords)


class CatchUpWithExtractiveSummaryEndpointTest(ZulipTestCase):
    def test_extractive_summary_included_when_requested(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.subscribe(hamlet, "Verona")
        self.subscribe(cordelia, "Verona")

        since = (timezone_now() - timedelta(hours=1)).isoformat()

        self.send_stream_message(
            cordelia, "Verona", "TODO: review the PR before Friday", topic_name="summary test"
        )
        self.send_stream_message(
            cordelia, "Verona", "The deployment is ready for review", topic_name="summary test"
        )

        self.login_user(hamlet)
        result = self.client_get(
            "/json/catch-up",
            {"since": since, "include_extractive_summary": "true"},
        )
        self.assert_json_success(result)

        data = result.json()
        topic = next(
            (t for t in data["topics"] if t["topic_name"] == "summary test"),
            None,
        )
        self.assertIsNotNone(topic)
        assert topic is not None

        # When extractive summary is requested, key_messages should be present.
        self.assertIn("key_messages", topic)
        self.assertIsInstance(topic["key_messages"], list)
        self.assertGreater(len(topic["key_messages"]), 0)

        # Keywords should also be present.
        self.assertIn("keywords", topic)
        self.assertIsInstance(topic["keywords"], list)

    def test_extractive_summary_not_included_by_default(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.subscribe(hamlet, "Verona")
        self.subscribe(cordelia, "Verona")

        since = (timezone_now() - timedelta(hours=1)).isoformat()
        self.send_stream_message(cordelia, "Verona", "hello", topic_name="no summary test")

        self.login_user(hamlet)
        result = self.client_get("/json/catch-up", {"since": since})
        self.assert_json_success(result)

        data = result.json()
        topic = next(
            (t for t in data["topics"] if t["topic_name"] == "no summary test"),
            None,
        )
        self.assertIsNotNone(topic)
        assert topic is not None

        # key_messages should NOT be present when not requested.
        self.assertNotIn("key_messages", topic)
