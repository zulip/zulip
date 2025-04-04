import time
from unittest import mock

import orjson
from django.utils.timezone import now as timezone_now

from zerver.actions.streams import do_change_stream_permission
from zerver.actions.user_topics import do_set_user_topic_visibility_policy
from zerver.lib.events import ClientCapabilities, do_events_register
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_topics import set_topic_visibility_policy, topic_has_visibility_policy
from zerver.models import Message, UserMessage, UserTopic
from zerver.models.clients import get_client
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream
from zerver.tornado.event_queue import allocate_client_descriptor


class TopicHistoryTest(ZulipTestCase):
    def test_topics_history_zephyr_mirror(self) -> None:
        user_profile = self.mit_user("sipbtest")
        stream_name = "new_stream"

        # Send a message to this new stream from another user
        self.subscribe(self.mit_user("starnine"), stream_name)
        stream = get_stream(stream_name, user_profile.realm)
        self.send_stream_message(self.mit_user("starnine"), stream_name, topic_name="secret topic")

        # Now subscribe this MIT user to the new stream and verify
        # that the new topic is not accessible
        self.login_user(user_profile)
        self.subscribe(user_profile, stream_name)
        endpoint = f"/json/users/me/{stream.id}/topics"
        result = self.client_get(endpoint, {}, subdomain="zephyr")
        history = self.assert_json_success(result)["topics"]
        self.assertEqual(history, [])

    def test_topics_history(self) -> None:
        # verified: int(UserMessage.flags.read) == 1
        user_profile = self.example_user("iago")
        self.login_user(user_profile)
        stream_name = "Verona"

        stream = get_stream(stream_name, user_profile.realm)
        recipient = stream.recipient

        def create_test_message(topic_name: str) -> int:
            # TODO: Clean this up to send messages the normal way.

            hamlet = self.example_user("hamlet")
            message = Message(
                sender=hamlet,
                recipient=recipient,
                realm=stream.realm,
                content="whatever",
                date_sent=timezone_now(),
                sending_client=get_client("whatever"),
            )
            message.set_topic_name(topic_name)
            message.save()

            UserMessage.objects.create(
                user_profile=user_profile,
                message=message,
                flags=0,
            )

            return message.id

        # our most recent topics are topic0, topic1, topic2

        # Create old messages with strange spellings.
        create_test_message("topic2")
        create_test_message("toPIc1")
        create_test_message("toPIc0")
        create_test_message("topic2")
        create_test_message("topic2")
        create_test_message("Topic2")

        # Create new messages
        topic2_msg_id = create_test_message("topic2")
        create_test_message("topic1")
        create_test_message("topic1")
        topic1_msg_id = create_test_message("topic1")
        topic0_msg_id = create_test_message("topic0")

        endpoint = f"/json/users/me/{stream.id}/topics"
        result = self.client_get(endpoint, {})
        history = self.assert_json_success(result)["topics"]

        # We only look at the most recent three topics, because
        # the prior fixture data may be unreliable.
        history = history[:3]

        self.assertEqual(
            [topic["name"] for topic in history],
            [
                "topic0",
                "topic1",
                "topic2",
            ],
        )

        self.assertEqual(
            [topic["max_id"] for topic in history],
            [
                topic0_msg_id,
                topic1_msg_id,
                topic2_msg_id,
            ],
        )

        # Now try as cordelia, who we imagine as a totally new user in
        # that she doesn't have UserMessage rows.  We should see the
        # same results for a public stream.
        self.login("cordelia")
        result = self.client_get(endpoint, {})
        history = self.assert_json_success(result)["topics"]

        # We only look at the most recent three topics, because
        # the prior fixture data may be unreliable.
        history = history[:3]

        self.assertEqual(
            [topic["name"] for topic in history],
            [
                "topic0",
                "topic1",
                "topic2",
            ],
        )
        self.assertIn("topic0", [topic["name"] for topic in history])

        self.assertEqual(
            [topic["max_id"] for topic in history],
            [
                topic0_msg_id,
                topic1_msg_id,
                topic2_msg_id,
            ],
        )

        # Now make stream private, but subscribe cordelia
        do_change_stream_permission(
            stream,
            invite_only=True,
            history_public_to_subscribers=False,
            is_web_public=False,
            acting_user=self.example_user("cordelia"),
        )
        self.subscribe(self.example_user("cordelia"), stream.name)

        result = self.client_get(endpoint, {})
        history = self.assert_json_success(result)["topics"]
        history = history[:3]

        # Cordelia doesn't have these recent history items when we
        # wasn't subscribed in her results.
        self.assertNotIn("topic0", [topic["name"] for topic in history])
        self.assertNotIn("topic1", [topic["name"] for topic in history])
        self.assertNotIn("topic2", [topic["name"] for topic in history])

    def test_bad_stream_id(self) -> None:
        self.login("iago")

        # non-sensible stream id
        endpoint = "/json/users/me/9999999999/topics"
        result = self.client_get(endpoint, {})
        self.assert_json_error(result, "Invalid channel ID")

        # out of realm
        bad_stream = self.make_stream(
            "mit_stream",
            realm=get_realm("zephyr"),
        )
        endpoint = f"/json/users/me/{bad_stream.id}/topics"
        result = self.client_get(endpoint, {})
        self.assert_json_error(result, "Invalid channel ID")

        # private stream to which I am not subscribed
        private_stream = self.make_stream(
            "private_stream",
            invite_only=True,
        )
        endpoint = f"/json/users/me/{private_stream.id}/topics"
        result = self.client_get(endpoint, {})
        self.assert_json_error(result, "Invalid channel ID")

    def test_get_topics_web_public_stream_web_public_request(self) -> None:
        iago = self.example_user("iago")
        stream = self.make_stream("web-public-stream", is_web_public=True)
        self.subscribe(iago, stream.name)

        for i in range(3):
            self.send_stream_message(iago, stream.name, topic_name="topic" + str(i))

        endpoint = f"/json/users/me/{stream.id}/topics"
        result = self.client_get(endpoint)
        history = self.assert_json_success(result)["topics"]
        self.assertEqual(
            [topic["name"] for topic in history],
            [
                "topic2",
                "topic1",
                "topic0",
            ],
        )

    def test_get_topics_non_web_public_stream_web_public_request(self) -> None:
        stream = get_stream("Verona", self.example_user("iago").realm)
        endpoint = f"/json/users/me/{stream.id}/topics"
        result = self.client_get(endpoint)
        self.assert_json_error(result, "Invalid channel ID", 400)

    def test_get_topics_non_existent_stream_web_public_request(self) -> None:
        non_existent_stream_id = 10000000000000000000000
        endpoint = f"/json/users/me/{non_existent_stream_id}/topics"
        result = self.client_get(endpoint)
        self.assert_json_error(result, "Invalid channel ID", 400)


class TopicDeleteTest(ZulipTestCase):
    def test_topic_delete(self) -> None:
        initial_last_msg_id = self.get_last_message().id
        stream_name = "new_stream"
        topic_name = "new topic 2"

        # NON-ADMIN USER
        user_profile = self.example_user("hamlet")
        self.subscribe(user_profile, stream_name)

        # Send message
        stream = get_stream(stream_name, user_profile.realm)
        self.send_stream_message(user_profile, stream_name, topic_name=topic_name)
        last_msg_id = self.send_stream_message(user_profile, stream_name, topic_name=topic_name)

        # Deleting the topic
        self.login_user(user_profile)
        endpoint = "/json/streams/" + str(stream.id) + "/delete_topic"
        result = self.client_post(
            endpoint,
            {
                "topic_name": topic_name,
            },
        )
        self.assert_json_error(result, "Must be an organization administrator")
        self.assertTrue(Message.objects.filter(id=last_msg_id).exists())

        # Make stream private with limited history
        do_change_stream_permission(
            stream,
            invite_only=True,
            history_public_to_subscribers=False,
            is_web_public=False,
            acting_user=user_profile,
        )

        # NON-ADMIN USER follows the topic
        set_topic_visibility_policy(
            user_profile, [[stream_name, topic_name]], UserTopic.VisibilityPolicy.FOLLOWED
        )

        # ADMIN USER subscribed now and follows the topic
        user_profile = self.example_user("iago")
        self.subscribe(user_profile, stream_name)
        self.login_user(user_profile)
        new_last_msg_id = self.send_stream_message(user_profile, stream_name, topic_name=topic_name)
        set_topic_visibility_policy(
            user_profile, [[stream_name, topic_name]], UserTopic.VisibilityPolicy.FOLLOWED
        )

        # Now admin deletes all messages in topic -- which should only
        # delete new_last_msg_id, i.e. the one sent since they joined.
        self.assertEqual(self.get_last_message().id, new_last_msg_id)
        result = self.client_post(
            endpoint,
            {
                "topic_name": topic_name,
            },
        )
        result_dict = self.assert_json_success(result)
        self.assertTrue(result_dict["complete"])
        self.assertTrue(Message.objects.filter(id=last_msg_id).exists())

        # Verify that we delete the UserTopic row only for 'iago' (ADMIN USER) as they can't
        # access any messages in the topic. 'hamlet' (NON ADMIN USER) can still access the
        # protected messages hence the UserTopic row for him is not deleted.
        self.assertTrue(
            topic_has_visibility_policy(
                self.example_user("hamlet"),
                stream.id,
                topic_name,
                UserTopic.VisibilityPolicy.FOLLOWED,
            )
        )
        self.assertFalse(
            topic_has_visibility_policy(
                self.example_user("iago"),
                stream.id,
                topic_name,
                UserTopic.VisibilityPolicy.FOLLOWED,
            )
        )

        # Try to delete all messages in the topic again. There are no messages accessible
        # to the administrator, so this should do nothing.
        result = self.client_post(
            endpoint,
            {
                "topic_name": topic_name,
            },
        )
        result_dict = self.assert_json_success(result)
        self.assertTrue(result_dict["complete"])
        self.assertTrue(Message.objects.filter(id=last_msg_id).exists())

        # Make the stream's history public to subscribers
        do_change_stream_permission(
            stream,
            invite_only=True,
            history_public_to_subscribers=True,
            is_web_public=False,
            acting_user=user_profile,
        )
        # Delete the topic should now remove all messages
        result = self.client_post(
            endpoint,
            {
                "topic_name": topic_name,
            },
        )
        result_dict = self.assert_json_success(result)
        self.assertTrue(result_dict["complete"])
        self.assertFalse(Message.objects.filter(id=last_msg_id).exists())
        self.assertTrue(Message.objects.filter(id=initial_last_msg_id).exists())

        # Delete again, to test the edge case of deleting an empty topic.
        result = self.client_post(
            endpoint,
            {
                "topic_name": topic_name,
            },
        )
        result_dict = self.assert_json_success(result)
        self.assertTrue(result_dict["complete"])
        self.assertFalse(Message.objects.filter(id=last_msg_id).exists())
        self.assertTrue(Message.objects.filter(id=initial_last_msg_id).exists())

    def test_topic_delete_timeout(self) -> None:
        stream_name = "new_stream"
        topic_name = "new topic 2"

        user_profile = self.example_user("iago")
        self.subscribe(user_profile, stream_name)

        stream = get_stream(stream_name, user_profile.realm)
        self.send_stream_message(user_profile, stream_name, topic_name=topic_name)

        self.login_user(user_profile)
        endpoint = "/json/streams/" + str(stream.id) + "/delete_topic"
        with mock.patch("time.monotonic", side_effect=[10000, 10051]):
            result = self.client_post(
                endpoint,
                {
                    "topic_name": topic_name,
                },
            )
            result_dict = self.assert_json_success(result)
            self.assertFalse(result_dict["complete"])


class EmptyTopicNameTest(ZulipTestCase):
    def test_client_supports_empty_topic_name(self) -> None:
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        queue_data = dict(
            all_public_streams=True,
            apply_markdown=True,
            client_type_name="website",
            empty_topic_name=True,
            event_types=[
                "message",
                "update_message",
                "delete_message",
                "user_topic",
                "typing",
                "update_message_flags",
            ],
            last_connection_time=time.time(),
            queue_timeout=600,
            realm_id=hamlet.realm.id,
            stream_typing_notifications=True,
            user_profile_id=hamlet.id,
        )
        client = allocate_client_descriptor(queue_data)
        self.assertTrue(client.event_queue.empty())

        message_id = self.send_stream_message(iago, "Denmark", topic_name="")
        events = client.event_queue.contents()
        self.assertEqual(events[0]["message"]["subject"], "")

        message_id_2 = self.send_stream_message(
            iago, "Denmark", topic_name=Message.EMPTY_TOPIC_FALLBACK_NAME
        )
        events = client.event_queue.contents()
        self.assertEqual(events[1]["message"]["subject"], "")

        self.login_user(iago)
        with self.captureOnCommitCallbacks(execute=True):
            params = {"topic": "new topic name", "send_notification_to_new_thread": "false"}
            self.client_patch(f"/json/messages/{message_id}", params)
            self.client_patch(f"/json/messages/{message_id_2}", params)
        events = client.event_queue.contents()
        self.assertEqual(events[2]["orig_subject"], "")
        self.assertEqual(events[3]["orig_subject"], "")

        # reset
        message_id = self.send_stream_message(
            iago, "Denmark", topic_name="", skip_capture_on_commit_callbacks=True
        )
        message_id_2 = self.send_stream_message(
            iago,
            "Verona",
            topic_name=Message.EMPTY_TOPIC_FALLBACK_NAME,
            skip_capture_on_commit_callbacks=True,
        )

        with self.captureOnCommitCallbacks(execute=True):
            self.client_delete(f"/json/messages/{message_id}")
            self.client_delete(f"/json/messages/{message_id_2}")
        events = client.event_queue.contents()
        self.assertEqual(events[4]["topic"], "")
        self.assertEqual(events[5]["topic"], "")

        # reset
        message_id = self.send_stream_message(
            iago, "Denmark", topic_name="", skip_capture_on_commit_callbacks=True
        )
        message_id_2 = self.send_stream_message(
            iago,
            "Verona",
            topic_name=Message.EMPTY_TOPIC_FALLBACK_NAME,
            skip_capture_on_commit_callbacks=True,
        )

        self.login_user(hamlet)
        denmark = get_stream("Denmark", hamlet.realm)
        verona = get_stream("Verona", hamlet.realm)
        with self.captureOnCommitCallbacks(execute=True):
            do_set_user_topic_visibility_policy(
                hamlet,
                denmark,
                "",
                visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
            )
            do_set_user_topic_visibility_policy(
                hamlet,
                verona,
                Message.EMPTY_TOPIC_FALLBACK_NAME,
                visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
            )
        events = client.event_queue.contents()
        self.assertEqual(events[6]["topic_name"], "")
        self.assertEqual(events[7]["topic_name"], "")

        params = dict(
            type="stream",
            op="start",
            stream_id=str(denmark.id),
            topic="",
        )
        self.api_post(hamlet, "/api/v1/typing", params)
        params = dict(
            type="stream",
            op="start",
            stream_id=str(verona.id),
            topic=Message.EMPTY_TOPIC_FALLBACK_NAME,
        )
        self.api_post(hamlet, "/api/v1/typing", params)
        events = client.event_queue.contents()
        self.assertEqual(events[8]["topic"], "")
        self.assertEqual(events[9]["topic"], "")

        # Prep to mark it as read before marking it as unread.
        params = {
            "messages": orjson.dumps([message_id, message_id_2]).decode(),
            "op": "add",
            "flag": "read",
        }
        self.client_post("/json/messages/flags", params)

        with self.captureOnCommitCallbacks(execute=True):
            params = {
                "messages": orjson.dumps([message_id, message_id_2]).decode(),
                "op": "remove",
                "flag": "read",
            }
            self.client_post("/json/messages/flags", params)
        events = client.event_queue.contents()
        self.assertEqual(events[10]["message_details"][str(message_id)]["topic"], "")
        self.assertEqual(events[10]["message_details"][str(message_id_2)]["topic"], "")

    def test_client_not_supports_empty_topic_name(self) -> None:
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        queue_data = dict(
            all_public_streams=True,
            apply_markdown=True,
            client_type_name="zulip-mobile",
            empty_topic_name=False,
            event_types=[
                "message",
                "update_message",
                "delete_message",
                "user_topic",
                "typing",
                "update_message_flags",
            ],
            last_connection_time=time.time(),
            queue_timeout=600,
            realm_id=hamlet.realm.id,
            stream_typing_notifications=True,
            user_profile_id=hamlet.id,
        )
        client = allocate_client_descriptor(queue_data)
        self.assertTrue(client.event_queue.empty())

        message_id = self.send_stream_message(iago, "Denmark", topic_name="")
        events = client.event_queue.contents()
        self.assertEqual(events[0]["message"]["subject"], Message.EMPTY_TOPIC_FALLBACK_NAME)

        message_id_2 = self.send_stream_message(
            iago, "Denmark", topic_name=Message.EMPTY_TOPIC_FALLBACK_NAME
        )
        events = client.event_queue.contents()
        self.assertEqual(events[1]["message"]["subject"], Message.EMPTY_TOPIC_FALLBACK_NAME)

        self.login_user(iago)
        with self.captureOnCommitCallbacks(execute=True):
            params = {"topic": "new topic name", "send_notification_to_new_thread": "false"}
            self.client_patch(f"/json/messages/{message_id}", params)
            self.client_patch(f"/json/messages/{message_id_2}", params)
        events = client.event_queue.contents()
        self.assertEqual(events[2]["orig_subject"], Message.EMPTY_TOPIC_FALLBACK_NAME)
        self.assertEqual(events[3]["orig_subject"], Message.EMPTY_TOPIC_FALLBACK_NAME)

        # reset
        message_id = self.send_stream_message(
            iago, "Denmark", topic_name="", skip_capture_on_commit_callbacks=True
        )
        message_id_2 = self.send_stream_message(
            iago,
            "Verona",
            topic_name=Message.EMPTY_TOPIC_FALLBACK_NAME,
            skip_capture_on_commit_callbacks=True,
        )

        with self.captureOnCommitCallbacks(execute=True):
            self.client_delete(f"/json/messages/{message_id}")
            self.client_delete(f"/json/messages/{message_id_2}")
        events = client.event_queue.contents()
        self.assertEqual(events[4]["topic"], Message.EMPTY_TOPIC_FALLBACK_NAME)
        self.assertEqual(events[5]["topic"], Message.EMPTY_TOPIC_FALLBACK_NAME)

        # reset
        message_id = self.send_stream_message(
            iago, "Denmark", topic_name="", skip_capture_on_commit_callbacks=True
        )
        message_id_2 = self.send_stream_message(
            iago,
            "Verona",
            topic_name=Message.EMPTY_TOPIC_FALLBACK_NAME,
            skip_capture_on_commit_callbacks=True,
        )

        self.login_user(hamlet)
        denmark = get_stream("Denmark", hamlet.realm)
        verona = get_stream("Verona", hamlet.realm)
        with self.captureOnCommitCallbacks(execute=True):
            do_set_user_topic_visibility_policy(
                hamlet,
                denmark,
                "",
                visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
            )
            do_set_user_topic_visibility_policy(
                hamlet,
                verona,
                Message.EMPTY_TOPIC_FALLBACK_NAME,
                visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
            )
        events = client.event_queue.contents()
        self.assertEqual(events[6]["topic_name"], Message.EMPTY_TOPIC_FALLBACK_NAME)
        self.assertEqual(events[7]["topic_name"], Message.EMPTY_TOPIC_FALLBACK_NAME)

        params = dict(
            type="stream",
            op="start",
            stream_id=str(denmark.id),
            topic="",
        )
        self.api_post(hamlet, "/api/v1/typing", params)
        params = dict(
            type="stream",
            op="start",
            stream_id=str(verona.id),
            topic=Message.EMPTY_TOPIC_FALLBACK_NAME,
        )
        self.api_post(hamlet, "/api/v1/typing", params)
        events = client.event_queue.contents()
        self.assertEqual(events[8]["topic"], Message.EMPTY_TOPIC_FALLBACK_NAME)
        self.assertEqual(events[9]["topic"], Message.EMPTY_TOPIC_FALLBACK_NAME)

        # Prep to mark it as read before marking it as unread.
        params = {
            "messages": orjson.dumps([message_id, message_id_2]).decode(),
            "op": "add",
            "flag": "read",
        }
        self.client_post("/json/messages/flags", params)

        with self.captureOnCommitCallbacks(execute=True):
            params = {
                "messages": orjson.dumps([message_id, message_id_2]).decode(),
                "op": "remove",
                "flag": "read",
            }
            self.client_post("/json/messages/flags", params)
        events = client.event_queue.contents()
        self.assertEqual(
            events[10]["message_details"][str(message_id)]["topic"],
            Message.EMPTY_TOPIC_FALLBACK_NAME,
        )
        self.assertEqual(
            events[10]["message_details"][str(message_id_2)]["topic"],
            Message.EMPTY_TOPIC_FALLBACK_NAME,
        )

    def test_fetch_messages(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        first_message_id = self.send_stream_message(hamlet, "Denmark", topic_name="")
        second_message_id = self.send_stream_message(
            hamlet, "Denmark", topic_name=Message.EMPTY_TOPIC_FALLBACK_NAME
        )

        # Fetch using `/messages` endpoint.
        params = {
            "allow_empty_topic_name": "false",
            "message_ids": orjson.dumps([first_message_id, second_message_id]).decode(),
        }
        result = self.client_get("/json/messages", params)
        data = self.assert_json_success(result)
        self.assert_length(data["messages"], 2)
        for message in data["messages"]:
            self.assertEqual(message["subject"], Message.EMPTY_TOPIC_FALLBACK_NAME)

        params = {
            "allow_empty_topic_name": "true",
            "message_ids": orjson.dumps([first_message_id, second_message_id]).decode(),
        }
        result = self.client_get("/json/messages", params)
        data = self.assert_json_success(result)
        self.assert_length(data["messages"], 2)
        for message in data["messages"]:
            self.assertEqual(message["subject"], "")

        get_params = {
            "allow_empty_topic_name": "false",
            "anchor": "newest",
            "num_before": 2,
            "num_after": 0,
            "narrow": orjson.dumps(
                [
                    {"operator": "channel", "operand": "Denmark"},
                    {"operator": "topic", "operand": Message.EMPTY_TOPIC_FALLBACK_NAME},
                ]
            ).decode(),
        }
        result = self.client_get("/json/messages", get_params)
        data = self.assert_json_success(result)
        self.assert_length(data["messages"], 2)
        for message in data["messages"]:
            self.assertEqual(message["subject"], Message.EMPTY_TOPIC_FALLBACK_NAME)

        # Fetch using `/messages/{message_id}` endpoint.
        result = self.client_get(
            f"/json/messages/{first_message_id}", {"allow_empty_topic_name": "false"}
        )
        data = self.assert_json_success(result)
        self.assertEqual(data["message"]["subject"], Message.EMPTY_TOPIC_FALLBACK_NAME)

        result = self.client_get(
            f"/json/messages/{second_message_id}", {"allow_empty_topic_name": "false"}
        )
        data = self.assert_json_success(result)
        self.assertEqual(data["message"]["subject"], Message.EMPTY_TOPIC_FALLBACK_NAME)

        result = self.client_get(
            f"/json/messages/{first_message_id}", {"allow_empty_topic_name": "true"}
        )
        data = self.assert_json_success(result)
        self.assertEqual(data["message"]["subject"], "")

        result = self.client_get(
            f"/json/messages/{second_message_id}", {"allow_empty_topic_name": "true"}
        )
        data = self.assert_json_success(result)
        self.assertEqual(data["message"]["subject"], "")

        # Verify `edit_history` objects.
        params = {"topic": "new topic name"}
        result = self.client_patch(f"/json/messages/{first_message_id}", params)
        self.assert_json_success(result)

        result = self.client_get(
            f"/json/messages/{first_message_id}", {"allow_empty_topic_name": "false"}
        )
        data = self.assert_json_success(result)
        self.assertEqual(
            data["message"]["edit_history"][0]["prev_topic"], Message.EMPTY_TOPIC_FALLBACK_NAME
        )

        result = self.client_get(
            f"/json/messages/{first_message_id}", {"allow_empty_topic_name": "true"}
        )
        data = self.assert_json_success(result)
        self.assertEqual(data["message"]["edit_history"][0]["prev_topic"], "")

        params = {"topic": ""}
        result = self.client_patch(f"/json/messages/{first_message_id}", params)
        self.assert_json_success(result)

        result = self.client_get(
            f"/json/messages/{first_message_id}", {"allow_empty_topic_name": "false"}
        )
        data = self.assert_json_success(result)
        self.assertEqual(
            data["message"]["edit_history"][0]["topic"], Message.EMPTY_TOPIC_FALLBACK_NAME
        )

        result = self.client_get(
            f"/json/messages/{first_message_id}", {"allow_empty_topic_name": "true"}
        )
        data = self.assert_json_success(result)
        self.assertEqual(data["message"]["edit_history"][0]["topic"], "")

    def test_get_message_edit_history(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        message_id = self.send_stream_message(hamlet, "Denmark", topic_name="")
        message_id_2 = self.send_stream_message(
            hamlet, "Denmark", topic_name=Message.EMPTY_TOPIC_FALLBACK_NAME
        )

        params = {"topic": "new topic name"}
        result = self.client_patch(f"/json/messages/{message_id}", params)
        self.assert_json_success(result)
        result = self.client_patch(f"/json/messages/{message_id_2}", params)
        self.assert_json_success(result)

        params = {"allow_empty_topic_name": "false"}
        result = self.client_get(f"/json/messages/{message_id}/history", params)
        data = self.assert_json_success(result)
        self.assertEqual(data["message_history"][0]["topic"], Message.EMPTY_TOPIC_FALLBACK_NAME)
        self.assertEqual(
            data["message_history"][1]["prev_topic"], Message.EMPTY_TOPIC_FALLBACK_NAME
        )

        result = self.client_get(f"/json/messages/{message_id_2}/history", params)
        data = self.assert_json_success(result)
        self.assertEqual(data["message_history"][0]["topic"], Message.EMPTY_TOPIC_FALLBACK_NAME)
        self.assertEqual(
            data["message_history"][1]["prev_topic"], Message.EMPTY_TOPIC_FALLBACK_NAME
        )

        params = {"allow_empty_topic_name": "true"}
        result = self.client_get(f"/json/messages/{message_id}/history", params)
        data = self.assert_json_success(result)
        self.assertEqual(data["message_history"][0]["topic"], "")
        self.assertEqual(data["message_history"][1]["prev_topic"], "")

        result = self.client_get(f"/json/messages/{message_id_2}/history", params)
        data = self.assert_json_success(result)
        self.assertEqual(data["message_history"][0]["topic"], "")
        self.assertEqual(data["message_history"][1]["prev_topic"], "")

    def test_initial_state_data(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        self.login_user(hamlet)

        self.send_stream_message(hamlet, "Denmark", topic_name="")
        self.send_stream_message(hamlet, "Verona", topic_name=Message.EMPTY_TOPIC_FALLBACK_NAME)

        do_set_user_topic_visibility_policy(
            iago,
            get_stream("Denmark", iago.realm),
            "",
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )
        do_set_user_topic_visibility_policy(
            iago,
            get_stream("Verona", iago.realm),
            Message.EMPTY_TOPIC_FALLBACK_NAME,
            visibility_policy=UserTopic.VisibilityPolicy.UNMUTED,
        )

        with mock.patch("zerver.lib.events.request_event_queue", return_value=1):
            state_data = do_events_register(
                iago,
                iago.realm,
                get_client("website"),
                client_capabilities=ClientCapabilities(
                    empty_topic_name=True, notification_settings_null=False
                ),
                fetch_event_types=["update_message_flags", "message", "user_topic"],
            )
        self.assertEqual(state_data["unread_msgs"]["streams"][0]["topic"], "")
        self.assertEqual(state_data["unread_msgs"]["streams"][1]["topic"], "")
        self.assertEqual(state_data["user_topics"][0]["topic_name"], "")
        self.assertEqual(state_data["user_topics"][1]["topic_name"], "")

        with mock.patch("zerver.lib.events.request_event_queue", return_value=1):
            state_data = do_events_register(
                iago,
                iago.realm,
                get_client("website"),
                client_capabilities=ClientCapabilities(
                    empty_topic_name=False, notification_settings_null=False
                ),
                fetch_event_types=["update_message_flags", "message", "user_topic"],
            )
        self.assertEqual(
            state_data["unread_msgs"]["streams"][0]["topic"], Message.EMPTY_TOPIC_FALLBACK_NAME
        )
        self.assertEqual(
            state_data["unread_msgs"]["streams"][1]["topic"], Message.EMPTY_TOPIC_FALLBACK_NAME
        )
        self.assertEqual(
            state_data["user_topics"][0]["topic_name"], Message.EMPTY_TOPIC_FALLBACK_NAME
        )
        self.assertEqual(
            state_data["user_topics"][1]["topic_name"], Message.EMPTY_TOPIC_FALLBACK_NAME
        )

    def test_get_channel_topics(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        channel_one = self.make_stream("channel_one")
        channel_two = self.make_stream("channel_two")
        self.subscribe(hamlet, channel_one.name)
        self.subscribe(hamlet, channel_two.name)

        self.send_stream_message(hamlet, channel_one.name, topic_name="")
        self.send_stream_message(
            hamlet, channel_two.name, topic_name=Message.EMPTY_TOPIC_FALLBACK_NAME
        )

        params = {"allow_empty_topic_name": "false"}
        for channel_id in [channel_one.id, channel_two.id]:
            result = self.client_get(f"/json/users/me/{channel_id}/topics", params)
            data = self.assert_json_success(result)
            self.assertEqual(data["topics"][0]["name"], Message.EMPTY_TOPIC_FALLBACK_NAME)

        params = {"allow_empty_topic_name": "true"}
        for channel_id in [channel_one.id, channel_two.id]:
            result = self.client_get(f"/json/users/me/{channel_id}/topics", params)
            data = self.assert_json_success(result)
            self.assertEqual(data["topics"][0]["name"], "")
