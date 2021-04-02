from unittest.mock import patch

import orjson

from zerver.lib.bot_lib import EmbeddedBotHandler, EmbeddedBotQuitException, EmbeddedBotValueError
from zerver.lib.exceptions import JsonableError
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import (
    Message,
    Reaction,
    UserProfile,
    get_display_recipient,
    get_realm,
    get_service_profile,
    get_user,
)


class TestEmbeddedBotMessaging(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user("othello")
        self.bot_profile = self.create_test_bot(
            "embedded",
            self.user_profile,
            full_name="Embedded bot",
            bot_type=UserProfile.EMBEDDED_BOT,
            service_name="helloworld",
            config_data=orjson.dumps({"foo": "bar"}).decode(),
        )
        self.incrementor_bot_profile = self.create_test_bot(
            "incrementor",
            self.user_profile,
            full_name="Incrementor Bot",
            bot_type=UserProfile.EMBEDDED_BOT,
            service_name="incrementor",
        )
        self.mock_bot_handler = EmbeddedBotHandler(self.bot_profile)

    def test_pm_to_embedded_bot(self) -> None:
        assert self.bot_profile is not None
        self.send_personal_message(self.user_profile, self.bot_profile, content="help")
        last_message = self.get_last_message()
        self.assertEqual(last_message.content, "beep boop")
        self.assertEqual(last_message.sender_id, self.bot_profile.id)
        display_recipient = get_display_recipient(last_message.recipient)
        assert isinstance(display_recipient, list)
        self.assert_length(display_recipient, 1)
        self.assertEqual(display_recipient[0]["email"], self.user_profile.email)

    def test_stream_message_to_embedded_bot(self) -> None:
        assert self.bot_profile is not None
        self.send_stream_message(
            self.user_profile,
            "Denmark",
            content=f"@**{self.bot_profile.full_name}** foo",
            topic_name="bar",
        )
        last_message = self.get_last_message()
        self.assertEqual(last_message.content, "beep boop")
        self.assertEqual(last_message.sender_id, self.bot_profile.id)
        self.assertEqual(last_message.topic_name(), "bar")
        display_recipient = get_display_recipient(last_message.recipient)
        self.assertEqual(display_recipient, "Denmark")

    def test_stream_message_not_to_embedded_bot(self) -> None:
        self.send_stream_message(self.user_profile, "Denmark", content="foo", topic_name="bar")
        last_message = self.get_last_message()
        self.assertEqual(last_message.content, "foo")

    def test_embedded_bot_react_to_stream_message(self) -> None:
        # For this test and the tests below for reaction, we expect receiving a reaction.
        # Because the helloworld bot is implemented to add an reaction to the message
        # we sent to the bot.
        assert self.bot_profile is not None
        self.send_stream_message(
            self.user_profile,
            "Denmark",
            content=f"@**{self.bot_profile.full_name}** foo",
            topic_name="bar",
        )
        user_message = self.get_second_to_last_message()
        self.assertTrue(
            Reaction.objects.filter(
                message=user_message,
            ).exists()
        )

    def test_embedded_bot_react_to_pm(self) -> None:
        assert self.bot_profile is not None
        self.send_personal_message(self.user_profile, self.bot_profile, content="help")
        user_message = self.get_second_to_last_message()
        self.assertTrue(
            Reaction.objects.filter(
                message=user_message,
            ).exists()
        )

    def test_embedded_bot_react_without_id(self) -> None:
        assert self.mock_bot_handler is not None
        with self.assertRaises(EmbeddedBotValueError) as err:
            self.mock_bot_handler.react({"content": "test"}, "wave")
        self.assertEqual(str(err.exception), "id key is missing from message")

    def test_embedded_bot_react_does_not_exist(self) -> None:
        assert self.mock_bot_handler is not None
        self.send_stream_message(self.user_profile, "Denmark", content="foo", topic_name="bar")
        last_message = self.get_last_message()
        message_id = last_message.id
        last_message.delete()
        with self.assertRaises(EmbeddedBotValueError) as err:
            self.mock_bot_handler.react({"id": message_id}, "wave")
        self.assertEqual(str(err.exception), "Message with the given ID does not exist")

    def test_embedded_bot_react_invalid_emoji(self) -> None:
        assert self.mock_bot_handler is not None
        with self.assertRaises(JsonableError) as err:
            self.mock_bot_handler.react({"id": 1}, "invalid_emoji")
        self.assertEqual(str(err.exception), "Emoji 'invalid_emoji' does not exist")

    def test_embedded_bot_update_message(self) -> None:
        assert self.incrementor_bot_profile is not None
        bot_reply_id = None
        for i in range(0, 5):
            self.send_stream_message(
                self.user_profile,
                "Denmark",
                content=f"@**{self.incrementor_bot_profile.full_name}** foo",
                topic_name="bar",
            )
            if bot_reply_id is None:
                bot_reply_id = self.get_last_message().id

        self.assertEqual(Message.objects.filter(id=bot_reply_id)[0].content, "5")

    def test_embedded_bot_update_message_without_message_id(self) -> None:
        assert self.mock_bot_handler is not None
        with self.assertRaises(EmbeddedBotValueError) as err:
            # "message_id" expected, but only "id" is given.
            self.mock_bot_handler.update_message({"id": "2", "content": "test"})
        self.assertEqual(str(err.exception), "message_id key is missing from message")

    def test_embedded_bot_update_message_with_jsonable_error(self) -> None:
        assert self.bot_profile is not None
        assert self.mock_bot_handler is not None
        self.send_stream_message(
            self.user_profile,
            "Denmark",
            content=f"@**{self.bot_profile.full_name}** foo",
            topic_name="bar",
        )
        user_message = self.get_second_to_last_message()
        with self.assertRaises(JsonableError) as err:
            self.mock_bot_handler.update_message({"message_id": user_message.id, "content": "test"})
        self.assertEqual(str(err.exception), "You don't have permission to edit this message")

    def test_embedded_bot_update_message_with_invalid_message_data(self) -> None:
        assert self.mock_bot_handler is not None
        with self.assertRaises(EmbeddedBotValueError):
            self.mock_bot_handler.update_message({"message_id": 1, "topic": 123})
        with self.assertRaises(EmbeddedBotValueError):
            self.mock_bot_handler.update_message(
                {"message_id": 1, "send_notification_to_old_thread": "invalid_bool"}
            )
        with self.assertRaises(EmbeddedBotValueError):
            self.mock_bot_handler.update_message(
                {"message_id": 1, "send_notification_to_new_thread": "invalid_bool"}
            )
        with self.assertRaises(EmbeddedBotValueError):
            self.mock_bot_handler.update_message({"message_id": 1, "propagate_mode": 123})
        with self.assertRaises(EmbeddedBotValueError):
            self.mock_bot_handler.update_message({"message_id": 1, "content": 123})

    def test_message_to_embedded_bot_with_initialize(self) -> None:
        assert self.bot_profile is not None
        with patch(
            "zulip_bots.bots.helloworld.helloworld.HelloWorldHandler.initialize", create=True
        ) as mock_initialize:
            self.send_stream_message(
                self.user_profile,
                "Denmark",
                content=f"@**{self.bot_profile.full_name}** foo",
                topic_name="bar",
            )
            mock_initialize.assert_called_once()

    def test_embedded_bot_quit_exception(self) -> None:
        assert self.bot_profile is not None
        with patch(
            "zulip_bots.bots.helloworld.helloworld.HelloWorldHandler.handle_message",
            side_effect=EmbeddedBotQuitException("I'm quitting!"),
        ):
            with self.assertLogs(level="WARNING") as m:
                self.send_stream_message(
                    self.user_profile,
                    "Denmark",
                    content=f"@**{self.bot_profile.full_name}** foo",
                    topic_name="bar",
                )
                self.assertEqual(m.output, ["WARNING:root:I'm quitting!"])


class TestEmbeddedBotFailures(ZulipTestCase):
    def test_message_embedded_bot_with_invalid_service(self) -> None:
        user_profile = self.example_user("othello")
        self.create_test_bot(
            short_name="embedded",
            user_profile=user_profile,
            bot_type=UserProfile.EMBEDDED_BOT,
            service_name="helloworld",
        )
        bot_profile = get_user("embedded-bot@zulip.testserver", get_realm("zulip"))
        service_profile = get_service_profile(bot_profile.id, "helloworld")
        service_profile.name = "invalid"
        service_profile.save()
        with self.assertLogs(level="ERROR") as m:
            self.send_stream_message(
                user_profile,
                "Denmark",
                content=f"@**{bot_profile.full_name}** foo",
                topic_name="bar",
            )
            self.assertEqual(
                m.output[0],
                f"ERROR:root:Error: User {bot_profile.id} has bot with invalid embedded bot service invalid",
            )
