import json
from collections.abc import Callable
from contextlib import nullcontext
from functools import wraps
from typing import Any, Concatenate
from unittest import mock

import responses
from typing_extensions import ParamSpec, override

from zerver.actions.message_send import get_message_triggered_bot_events
from zerver.actions.users import do_update_bot_service
from zerver.lib.bot_lib import BOT_SERVICE_TRIGGER_EVENT_NAME
from zerver.lib.integrations import EMBEDDED_BOTS
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import mock_queue_publish
from zerver.models import Recipient, UserProfile
from zerver.models.bots import Service, get_bot_services
from zerver.models.messages import UserMessage

BOT_TYPE_TO_QUEUE_NAME = {
    UserProfile.OUTGOING_WEBHOOK_BOT: "outgoing_webhooks",
    UserProfile.EMBEDDED_BOT: "embedded_bots",
}


class TestMessageTriggeredBotBasics(ZulipTestCase):
    def _get_outgoing_bot(self) -> UserProfile:
        outgoing_bot = self.create_test_bot(
            "bar",
            self.example_user("cordelia"),
            full_name="BarBot",
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
        )

        return outgoing_bot

    def test_message_triggered_bot_events_for_direct_messages(self) -> None:
        sender = self.example_user("hamlet")
        assert not sender.is_bot

        outgoing_bot = self._get_outgoing_bot()
        assert outgoing_bot.bot_type is not None

        event_dict = get_message_triggered_bot_events(
            sender=sender,
            message_triggered_bot_tuples=[
                (outgoing_bot.id, outgoing_bot.bot_type),
            ],
            active_user_ids={outgoing_bot.id},
            mentioned_user_ids=set(),
            recipient_type=Recipient.DIRECT_MESSAGE_GROUP,
        )

        expected = dict(
            outgoing_webhooks=[
                dict(
                    received_trigger_events=[Service.BOT_TRIGGER_DMS_RECEIVED],
                    user_profile_id=outgoing_bot.id,
                ),
            ],
        )

        self.assertEqual(event_dict, expected)

    def test_spurious_mentions(self) -> None:
        sender = self.example_user("hamlet")
        assert not sender.is_bot

        outgoing_bot = self._get_outgoing_bot()
        assert outgoing_bot.bot_type is not None

        # If outgoing_bot is not in mentioned_user_ids,
        # we will skip over it.  This tests an anomaly
        # of the code that our query for bots can include
        # bots that may not actually be mentioned, and it's
        # easiest to just filter them in get_message_triggered_bot_events.
        event_dict = get_message_triggered_bot_events(
            sender=sender,
            message_triggered_bot_tuples=[
                (outgoing_bot.id, outgoing_bot.bot_type),
            ],
            active_user_ids={outgoing_bot.id},
            mentioned_user_ids=set(),
            recipient_type=Recipient.STREAM,
        )

        self.assert_length(event_dict, 0)

    def test_message_triggered_bot_events_for_channel_mentions(self) -> None:
        sender = self.example_user("hamlet")
        assert not sender.is_bot

        outgoing_bot = self._get_outgoing_bot()
        assert outgoing_bot.bot_type is not None

        cordelia = self.example_user("cordelia")

        red_herring_bot = self.create_test_bot(
            short_name="whatever",
            user_profile=cordelia,
        )

        event_dict = get_message_triggered_bot_events(
            sender=sender,
            message_triggered_bot_tuples=[
                (outgoing_bot.id, outgoing_bot.bot_type),
                (red_herring_bot.id, UserProfile.OUTGOING_WEBHOOK_BOT),
            ],
            active_user_ids=set(),
            mentioned_user_ids={outgoing_bot.id},
            recipient_type=Recipient.STREAM,
        )

        expected = dict(
            outgoing_webhooks=[
                dict(
                    received_trigger_events=[Service.BOT_TRIGGER_ALL_DIRECT_MENTIONS],
                    user_profile_id=outgoing_bot.id,
                ),
            ],
        )

        self.assertEqual(event_dict, expected)

    def test_no_bot_events_when_mentioned_without_being_recipient(self) -> None:
        """Message-triggered bots should not get access to mentions if they
        aren't a direct recipient."""
        sender = self.example_user("hamlet")
        assert not sender.is_bot

        outgoing_bot = self._get_outgoing_bot()
        assert outgoing_bot.bot_type is not None

        event_dict = get_message_triggered_bot_events(
            sender=sender,
            message_triggered_bot_tuples=[
                (outgoing_bot.id, outgoing_bot.bot_type),
            ],
            active_user_ids=set(),
            mentioned_user_ids={outgoing_bot.id},
            recipient_type=Recipient.DIRECT_MESSAGE_GROUP,
        )

        self.assert_length(event_dict, 0)

    def test_message_triggered_bot_events_with_unexpected_bot_type(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        bot = self.create_test_bot(
            short_name="whatever",
            user_profile=cordelia,
        )
        wrong_bot_type = UserProfile.INCOMING_WEBHOOK_BOT
        bot.bot_type = wrong_bot_type
        bot.save()

        with self.assertLogs(level="ERROR") as m:
            event_dict = get_message_triggered_bot_events(
                sender=hamlet,
                message_triggered_bot_tuples=[
                    (bot.id, wrong_bot_type),
                ],
                active_user_ids=set(),
                mentioned_user_ids={bot.id},
                recipient_type=Recipient.DIRECT_MESSAGE_GROUP,
            )

        self.assert_length(event_dict, 0)
        self.assertEqual(
            m.output,
            [
                f"ERROR:root:Unexpected bot_type for message-triggered bot id={bot.id}: {wrong_bot_type}"
            ],
        )


ParamT = ParamSpec("ParamT")


def for_all_bot_types(
    test_func: Callable[Concatenate["TestMessageTriggeredBotEventTriggers", ParamT], None],
) -> Callable[Concatenate["TestMessageTriggeredBotEventTriggers", ParamT], None]:
    @wraps(test_func)
    def _wrapped(
        self: "TestMessageTriggeredBotEventTriggers", /, *args: ParamT.args, **kwargs: ParamT.kwargs
    ) -> None:
        for bot_type in BOT_TYPE_TO_QUEUE_NAME:
            self.bot_profile.bot_type = bot_type
            self.bot_profile.save()
            if bot_type == UserProfile.EMBEDDED_BOT:
                service = get_bot_services(self.bot_profile.id)[0]
                service.name = EMBEDDED_BOTS[0].name
                service.save()

            test_func(self, *args, **kwargs)

    return _wrapped


def patch_queue_publish(
    method_to_patch: str,
) -> Callable[
    [Callable[["TestMessageTriggeredBotEventTriggers", mock.Mock], None]],
    Callable[["TestMessageTriggeredBotEventTriggers"], None],
]:
    def inner(
        func: Callable[["TestMessageTriggeredBotEventTriggers", mock.Mock], None],
    ) -> Callable[["TestMessageTriggeredBotEventTriggers"], None]:
        @wraps(func)
        def _wrapped(self: "TestMessageTriggeredBotEventTriggers") -> None:
            with mock_queue_publish(method_to_patch) as m:
                func(self, m)

        return _wrapped

    return inner


class TestMessageTriggeredBotEventTriggers(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user("othello")
        self.bot_profile = self.create_test_bot(
            "foo",
            self.user_profile,
            full_name="FooBot",
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            payload_url='"https://bot.example.com/"',
        )
        self.second_bot_profile = self.create_test_bot(
            "bar",
            self.user_profile,
            full_name="BarBot",
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            payload_url='"https://bot.example.com/"',
        )

    @for_all_bot_types
    @patch_queue_publish("zerver.actions.message_send.queue_event_on_commit")
    def test_trigger_on_stream_mention_from_user(
        self, mock_queue_event_on_commit: mock.Mock
    ) -> None:
        content = "@**FooBot** foo bar!!!"
        recipient = "Denmark"
        recipient_type = "stream"

        def check_values_passed(
            queue_name: Any,
            trigger_event: dict[str, Any],
            processor: Callable[[Any], None] | None = None,
        ) -> None:
            assert self.bot_profile.bot_type
            self.assertEqual(queue_name, BOT_TYPE_TO_QUEUE_NAME[self.bot_profile.bot_type])
            self.assertEqual(trigger_event["message"]["content"], content)
            self.assertEqual(trigger_event["message"]["display_recipient"], recipient)
            self.assertEqual(trigger_event["message"]["sender_email"], self.user_profile.email)
            self.assertEqual(trigger_event["message"]["type"], recipient_type)
            self.assertEqual(
                trigger_event["received_trigger_events"], [Service.BOT_TRIGGER_ALL_DIRECT_MENTIONS]
            )
            self.assertEqual(trigger_event["user_profile_id"], self.bot_profile.id)

        mock_queue_event_on_commit.side_effect = check_values_passed

        self.send_stream_message(self.user_profile, "Denmark", content)
        self.assertTrue(mock_queue_event_on_commit.called)

    @patch_queue_publish("zerver.actions.message_send.queue_event_on_commit")
    def test_no_trigger_on_stream_message_without_mention(
        self, mock_queue_event_on_commit: mock.Mock
    ) -> None:
        sender = self.user_profile
        self.send_stream_message(sender, "Denmark")
        self.assertFalse(mock_queue_event_on_commit.called)

    @for_all_bot_types
    @patch_queue_publish("zerver.actions.message_send.queue_event_on_commit")
    def test_no_trigger_on_stream_mention_from_bot(
        self, mock_queue_event_on_commit: mock.Mock
    ) -> None:
        self.send_stream_message(self.second_bot_profile, "Denmark", "@**FooBot** foo bar!!!")
        self.assertFalse(mock_queue_event_on_commit.called)

    @for_all_bot_types
    @patch_queue_publish("zerver.actions.message_send.queue_event_on_commit")
    def test_no_trigger_on_mention_from_bot_with_no_trigger(
        self, mock_queue_event_on_commit: mock.Mock
    ) -> None:
        foo_bot = self.bot_profile
        # No trigger if the bot doesn't have the "all_direct_mentions" trigger.
        # Set the bots' trigger to only "dms_received".
        do_update_bot_service(
            foo_bot,
            interface=1,
            base_url="https://bot.example.com/",
            triggers=[Service.BOT_TRIGGER_DMS_RECEIVED],
            acting_user=None,
        )
        self.send_stream_message(self.second_bot_profile, "Denmark", "@**FooBot** foo bar!!!")
        self.assertFalse(mock_queue_event_on_commit.called)

    @for_all_bot_types
    @patch_queue_publish("zerver.actions.message_send.queue_event_on_commit")
    def test_trigger_on_personal_message_from_user(
        self, mock_queue_event_on_commit: mock.Mock
    ) -> None:
        sender = self.user_profile
        recipient = self.bot_profile

        def check_values_passed(
            queue_name: Any,
            trigger_event: dict[str, Any],
            processor: Callable[[Any], None] | None = None,
        ) -> None:
            assert self.bot_profile.bot_type
            self.assertEqual(queue_name, BOT_TYPE_TO_QUEUE_NAME[self.bot_profile.bot_type])
            self.assertEqual(trigger_event["user_profile_id"], self.bot_profile.id)
            self.assertEqual(
                trigger_event["received_trigger_events"], [Service.BOT_TRIGGER_DMS_RECEIVED]
            )
            self.assertEqual(trigger_event["message"]["sender_email"], sender.email)
            display_recipients = [
                trigger_event["message"]["display_recipient"][0]["email"],
                trigger_event["message"]["display_recipient"][1]["email"],
            ]
            self.assertTrue(sender.email in display_recipients)
            self.assertTrue(recipient.email in display_recipients)

        mock_queue_event_on_commit.side_effect = check_values_passed

        self.send_personal_message(sender, recipient, "test")
        self.assertTrue(mock_queue_event_on_commit.called)

    @for_all_bot_types
    @patch_queue_publish("zerver.actions.message_send.queue_event_on_commit")
    def test_no_trigger_on_personal_message_from_bot(
        self, mock_queue_event_on_commit: mock.Mock
    ) -> None:
        sender = self.second_bot_profile
        recipient = self.bot_profile
        self.send_personal_message(sender, recipient)
        self.assertFalse(mock_queue_event_on_commit.called)

    @for_all_bot_types
    @patch_queue_publish("zerver.actions.message_send.queue_event_on_commit")
    def test_trigger_on_group_direct_message_from_user(
        self, mock_queue_event_on_commit: mock.Mock
    ) -> None:
        self.second_bot_profile.bot_type = self.bot_profile.bot_type
        self.second_bot_profile.save()

        sender = self.user_profile
        recipients = [self.bot_profile, self.second_bot_profile]
        profile_ids = [self.bot_profile.id, self.second_bot_profile.id]

        def check_values_passed(
            queue_name: Any,
            trigger_event: dict[str, Any],
            processor: Callable[[Any], None] | None = None,
        ) -> None:
            assert self.bot_profile.bot_type
            self.assertEqual(queue_name, BOT_TYPE_TO_QUEUE_NAME[self.bot_profile.bot_type])
            self.assertIn(trigger_event["user_profile_id"], profile_ids)
            profile_ids.remove(trigger_event["user_profile_id"])
            self.assertEqual(
                trigger_event["received_trigger_events"], [Service.BOT_TRIGGER_DMS_RECEIVED]
            )
            self.assertEqual(trigger_event["message"]["sender_email"], sender.email)
            self.assertEqual(trigger_event["message"]["type"], "private")

        mock_queue_event_on_commit.side_effect = check_values_passed

        self.send_group_direct_message(sender, recipients, "test")
        self.assertEqual(mock_queue_event_on_commit.call_count, 2)

    @for_all_bot_types
    @patch_queue_publish("zerver.actions.message_send.queue_event_on_commit")
    def test_no_trigger_on_group_direct_message_from_bot(
        self, mock_queue_event_on_commit: mock.Mock
    ) -> None:
        sender = self.second_bot_profile
        recipients = [self.user_profile, self.bot_profile]
        self.send_group_direct_message(sender, recipients)
        self.assertFalse(mock_queue_event_on_commit.called)

    @responses.activate
    @for_all_bot_types
    def test_no_trigger_when_bot_lacks_relevant_triggers(self) -> None:
        sender = self.user_profile
        recipient = self.bot_profile
        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json="",
        )
        # No response when direct messaged if the bot doesn't have
        # the appropriate trigger.
        do_update_bot_service(
            recipient,
            interface=1,
            base_url="https://bot.example.com/",
            triggers=[Service.BOT_TRIGGER_ALL_DIRECT_MENTIONS],
            acting_user=None,
        )
        service = get_bot_services(recipient.id)[0]
        assert service.triggers == [Service.BOT_TRIGGER_ALL_DIRECT_MENTIONS]

        message_id = self.send_personal_message(sender, recipient)
        bot_user_message = UserMessage.objects.get(
            user_profile=self.bot_profile, message=message_id
        )
        self.assertNotIn("read", bot_user_message.flags_list())

        # No response when mentioned if the bot doesn't have the
        # appropriate trigger.
        do_update_bot_service(
            recipient,
            interface=1,
            base_url="https://bot.example.com/",
            triggers=[Service.BOT_TRIGGER_DMS_RECEIVED],
            acting_user=None,
        )
        service = get_bot_services(recipient.id)[0]
        assert service.triggers == [Service.BOT_TRIGGER_DMS_RECEIVED]

        channel = "Denmark"
        self.subscribe(self.bot_profile, channel)
        self.subscribe(sender, channel)
        message_id = self.send_stream_message(sender, channel, "@**FooBot** foo bar!!!")
        bot_user_message = UserMessage.objects.get(
            user_profile=self.bot_profile, message=message_id
        )
        self.assertNotIn("read", bot_user_message.flags_list())

    @responses.activate
    @for_all_bot_types
    def test_message_flagged_read_after_bot_processes_event(self) -> None:
        """
        Verifies that once an event has been processed by the message-triggered
        bot's queue processor, the message is marked as processed (flagged with
        `read`).
        """
        sender = self.user_profile
        recipients = [self.user_profile, self.bot_profile, self.second_bot_profile]
        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json="",
        )
        with self.assertLogs(level="INFO"):
            message_id = self.send_group_direct_message(
                sender, recipients, content=f"@**{self.bot_profile.full_name}** foo"
            )

        bot_user_message = UserMessage.objects.get(
            user_profile=self.bot_profile, message=message_id
        )
        self.assertIn("read", bot_user_message.flags_list())

    @responses.activate
    @for_all_bot_types
    def test_no_bot_message_read_flag_when_no_service_triggered(self) -> None:
        """
        Verifies that when a send message event doesn't trigger a bot's service,
        the message isn't flagged as read."
        """
        sender = self.user_profile

        service = get_bot_services(self.bot_profile.id)[0]
        service.triggers = [Service.BOT_TRIGGER_DMS_RECEIVED]
        service.save()

        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json="",
        )
        channel = "Denmark"
        self.subscribe(sender, channel)
        self.subscribe(self.bot_profile, channel)
        with self.assertNoLogs(level="INFO"):
            message_id = self.send_stream_message(
                sender, channel, content=f"@**{self.bot_profile.full_name}** foo"
            )

        bot_user_message = UserMessage.objects.get(
            user_profile=self.bot_profile, message=message_id
        )
        self.assertNotIn("read", bot_user_message.flags_list())

    @responses.activate
    @for_all_bot_types
    def test_direct_mention_to_bot_with_multiple_triggers(self) -> None:
        sender = self.user_profile
        service = get_bot_services(self.bot_profile.id)[0]
        self.assertListEqual(
            sorted(service.triggers),
            sorted([Service.BOT_TRIGGER_ALL_DIRECT_MENTIONS, Service.BOT_TRIGGER_DMS_RECEIVED]),
        )

        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json="",
        )
        ctx = (
            self.assertLogs(level="INFO")
            if self.bot_profile.bot_type == UserProfile.OUTGOING_WEBHOOK_BOT
            else nullcontext()
        )

        channel = "Denmark"
        channel_mention = f"@**{self.bot_profile.full_name}** foo"

        with ctx:
            self.send_stream_message(sender, channel, content=channel_mention)

        request = responses.calls[0].request
        assert request.body is not None
        payload = json.loads(request.body)

        self.assertEqual(
            payload["trigger"],
            BOT_SERVICE_TRIGGER_EVENT_NAME[Service.BOT_TRIGGER_ALL_DIRECT_MENTIONS],
        )
        self.assertEqual(payload["message"]["content"], channel_mention)
        self.assertEqual(payload["bot_email"], self.bot_profile.email)

    @responses.activate
    @for_all_bot_types
    def test_dm_to_bot_with_multiple_triggers(self) -> None:
        sender = self.user_profile
        service = get_bot_services(self.bot_profile.id)[0]
        self.assertListEqual(
            sorted(service.triggers),
            sorted([Service.BOT_TRIGGER_ALL_DIRECT_MENTIONS, Service.BOT_TRIGGER_DMS_RECEIVED]),
        )

        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json="",
        )
        ctx = (
            self.assertLogs(level="INFO")
            if self.bot_profile.bot_type == UserProfile.OUTGOING_WEBHOOK_BOT
            else nullcontext()
        )
        recipients = [self.user_profile, self.bot_profile]
        dm_content = "hello, this is a direct message"
        with ctx:
            self.send_group_direct_message(sender, recipients, content=dm_content)

        request = responses.calls[0].request
        assert request.body is not None
        payload = json.loads(request.body)

        self.assertEqual(
            payload["trigger"],
            BOT_SERVICE_TRIGGER_EVENT_NAME[Service.BOT_TRIGGER_DMS_RECEIVED],
        )
        self.assertEqual(payload["message"]["content"], dm_content)
        self.assertEqual(payload["bot_email"], self.bot_profile.email)

    @responses.activate
    @for_all_bot_types
    def test_old_bot_with_no_configured_triggers(self) -> None:
        """
        Verifies that message-triggered bots created before the multiple-triggers
        system was implemented are treated like they have the default triggers
        (`get_default_bot_triggers`)
        """
        sender = self.user_profile
        recipients = [self.user_profile, self.bot_profile]
        service = get_bot_services(self.bot_profile.id)[0]
        service.triggers = []
        service.save()
        self.assertListEqual(
            sorted(service.triggers),
            sorted([]),
        )

        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json="",
        )
        ctx = (
            self.assertLogs(level="INFO")
            if self.bot_profile.bot_type == UserProfile.OUTGOING_WEBHOOK_BOT
            else nullcontext()
        )

        with ctx:
            message_id = self.send_group_direct_message(
                sender,
                recipients,
                content="hello, this is a direct message",
            )
        bot_user_message = UserMessage.objects.get(
            user_profile=self.bot_profile, message=message_id
        )
        self.assertIn("read", bot_user_message.flags_list())

        channel = "Denmark"
        self.subscribe(self.bot_profile, channel)
        self.subscribe(self.user_profile, channel)

        with ctx:
            message_id = self.send_stream_message(
                self.user_profile,
                channel,
                content=f"@**{self.bot_profile.full_name}** foo",
            )
        bot_user_message = UserMessage.objects.get(
            user_profile=self.bot_profile, message=message_id
        )
        self.assertIn("read", bot_user_message.flags_list())
