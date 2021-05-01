from typing import Any, Dict

import orjson

from zerver.lib.actions import do_change_stream_invite_only
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile


class ZcommandTest(ZulipTestCase):
    def test_invalid_zcommand(self) -> None:
        self.login("hamlet")

        payload = dict(command="/boil-ocean")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_error(result, "No such command: boil-ocean")

        payload = dict(command="boil-ocean")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_error(result, "There should be a leading slash in the zcommand.")

    def test_ping_zcommand(self) -> None:
        self.login("hamlet")

        payload = dict(command="/ping")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)

    def test_night_zcommand(self) -> None:
        self.login("hamlet")
        user = self.example_user("hamlet")
        user.color_scheme = UserProfile.COLOR_SCHEME_LIGHT
        user.save()

        payload = dict(command="/night")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn("Changed to night", result.json()["msg"])

        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn("still in night mode", result.json()["msg"])

    def test_day_zcommand(self) -> None:
        self.login("hamlet")
        user = self.example_user("hamlet")
        user.color_scheme = UserProfile.COLOR_SCHEME_NIGHT
        user.save()

        payload = dict(command="/day")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn("Changed to day", result.json()["msg"])

        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assertIn("still in day mode", result.json()["msg"])

    def test_fluid_zcommand(self) -> None:
        self.login("hamlet")
        user = self.example_user("hamlet")
        user.fluid_layout_width = False
        user.save()

        payload = dict(command="/fluid-width")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assert_in_response("Changed to fluid-width mode!", result)

        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assert_in_response("You are still in fluid width mode", result)

    def test_fixed_zcommand(self) -> None:
        self.login("hamlet")
        user = self.example_user("hamlet")
        user.fluid_layout_width = True
        user.save()

        payload = dict(command="/fixed-width")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assert_in_response("Changed to fixed-width mode!", result)

        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        self.assert_in_response("You are still in fixed width mode", result)

    def get_digress_payload(self, data: Dict[str, str]) -> Dict[str, Any]:
        return dict(
            command="/digress",
            command_data=orjson.dumps(data).decode(),
        )

    def test_digress_incomplete_data(self) -> None:
        self.login("hamlet")
        payload = self.get_digress_payload(dict(old_stream="general"))
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_error(result, "Invalid data.")

    def test_digress_same_thread(self) -> None:
        self.login("hamlet")
        payload = self.get_digress_payload(
            dict(
                old_stream="general",
                old_topic="old topic name",
                new_stream="general",
                new_topic="old topic name",
            )
        )
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_error(result, "Cannot digress to the same topic.")

    def test_digress_from_public_stream(self) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        self.make_stream("general")
        self.subscribe(hamlet, "general")
        self.make_stream("test")
        self.subscribe(hamlet, "test")
        payload = self.get_digress_payload(
            dict(
                old_stream="general",
                old_topic="old topic name",
                new_stream="test",
                new_topic="new topic name",
            )
        )

        # Empty topic.
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_error(result, "Old topic #**general>old topic name** does not exist.")

        self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": "general",
                "client": "test suite",
                "content": "Test message",
                "topic": "old topic name",
            },
        )

        # Happy path.
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        message = self.get_last_message()
        self.assertEqual(message.topic_name(), "old topic name")
        self.assertEqual(
            message.content,
            f"@_**King Hamlet|{hamlet.id}** digressed to the new topic: #**test>new topic name**",
        )

        message = self.get_second_to_last_message()
        self.assertEqual(message.topic_name(), "new topic name")
        self.assertEqual(
            message.content,
            f"@_**King Hamlet|{hamlet.id}** digressed this from old topic: #**general>old topic name**",
        )

    def test_digress_from_private_stream_with_shared_history(self) -> None:
        # Data setup.
        self.login("hamlet")
        desdemona = self.example_user("desdemona")
        hamlet = self.example_user("hamlet")
        general = self.make_stream("general")
        self.subscribe(desdemona, "general")
        self.make_stream("test")
        self.subscribe(hamlet, "test")
        payload = self.get_digress_payload(
            dict(
                old_stream="general",
                old_topic="old topic name",
                new_stream="test",
                new_topic="new topic name",
            )
        )
        do_change_stream_invite_only(general, invite_only=True, history_public_to_subscribers=True)

        # Inaccessible stream.
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_error(result, "Invalid stream name 'general'")

        # Accessible stream, empty topic.
        self.subscribe(hamlet, "general")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_error(result, "Old topic #**general>old topic name** does not exist.")

        # Have Desmodena send a message to #general while Hamlet was not subscribed,
        # to make sure Hamlet does not have a UserMessage object.
        # Hamlet should still be able to digress, because history is visible.
        self.unsubscribe(hamlet, "general")
        self.login("desdemona")
        self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": "general",
                "client": "test suite",
                "content": "Test message",
                "topic": "old topic name",
            },
        )
        self.login("hamlet")
        self.subscribe(hamlet, "general")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        message = self.get_last_message()
        self.assertEqual(message.topic_name(), "old topic name")
        self.assertEqual(
            message.content,
            f"@_**King Hamlet|{hamlet.id}** digressed to the new topic: #**test>new topic name**",
        )

        message = self.get_second_to_last_message()
        self.assertEqual(message.topic_name(), "new topic name")
        self.assertEqual(
            message.content,
            f"@_**King Hamlet|{hamlet.id}** digressed this from old topic: #**general>old topic name**",
        )

    def test_digress_from_private_stream_with_protected_history(self) -> None:
        # Data setup.
        self.login("hamlet")
        desdemona = self.example_user("desdemona")
        hamlet = self.example_user("hamlet")
        general = self.make_stream("general")
        self.subscribe(desdemona, "general")
        self.make_stream("test")
        self.subscribe(hamlet, "test")
        payload = self.get_digress_payload(
            dict(
                old_stream="general",
                old_topic="old topic name",
                new_stream="test",
                new_topic="new topic name",
            )
        )
        do_change_stream_invite_only(general, invite_only=True, history_public_to_subscribers=False)

        # Inaccessible stream.
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_error(result, "Invalid stream name 'general'")

        # Accessible stream, empty topic.
        self.subscribe(hamlet, "general")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_error(result, "Old topic #**general>old topic name** does not exist.")

        # Have Desmodena send a message to #general while Hamlet was not subscribed,
        # to make sure Hamlet does not have a UserMessage object.
        # Hamlet should not be able to digress, because the old topic is technically
        # empty (for Hamlet).
        self.unsubscribe(hamlet, "general")
        self.login("desdemona")
        self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": "general",
                "client": "test suite",
                "content": "Test message",
                "topic": "old topic name",
            },
        )
        self.login("hamlet")
        self.subscribe(hamlet, "general")
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_error(result, "Old topic #**general>old topic name** does not exist.")

        # Message sent while Hamlet is subscribed.
        self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": "general",
                "client": "test suite",
                "content": "Test message",
                "topic": "old topic name",
            },
        )
        # Happy path.
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        message = self.get_last_message()
        self.assertEqual(message.topic_name(), "old topic name")
        self.assertEqual(
            message.content,
            f"@_**King Hamlet|{hamlet.id}** digressed to the new topic: #**test>new topic name**",
        )

        message = self.get_second_to_last_message()
        self.assertEqual(message.topic_name(), "new topic name")
        self.assertEqual(
            message.content,
            f"@_**King Hamlet|{hamlet.id}** digressed this from old topic: #**general>old topic name**",
        )

    def test_digress_new_topic_cleaned(self) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        self.make_stream("general")
        self.make_stream("test")
        self.subscribe(hamlet, "test")
        self.client_post(
            "/json/messages",
            {
                "type": "stream",
                "to": "general",
                "client": "test suite",
                "content": "Test message",
                "topic": "old topic name",
            },
        )
        payload = self.get_digress_payload(
            dict(
                old_stream="general",
                old_topic="old topic name",
                new_stream="test",
                new_topic=" This topic is really really really really really really really long.",
            )
        )
        result = self.client_post("/json/zcommand", payload)
        self.assert_json_success(result)
        message = self.get_second_to_last_message()
        self.assertEqual(
            message.topic_name(), "This topic is really really really really really really ..."
        )
