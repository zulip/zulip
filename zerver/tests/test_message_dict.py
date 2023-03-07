from typing import Any, Dict, List, Union
from unittest import mock

from django.utils.timezone import now as timezone_now

from zerver.lib.cache import cache_delete, to_dict_cache_key_id
from zerver.lib.markdown import version as markdown_version
from zerver.lib.message import MessageDict, messages_for_ids, sew_messages_and_reactions
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import make_client
from zerver.lib.topic import TOPIC_LINKS
from zerver.lib.types import DisplayRecipientT, UserDisplayRecipient
from zerver.models import (
    Message,
    Reaction,
    Realm,
    RealmFilter,
    Recipient,
    Stream,
    UserProfile,
    flush_per_request_caches,
    get_display_recipient,
    get_realm,
    get_stream,
)


class MessageDictTest(ZulipTestCase):
    def test_both_codepaths(self) -> None:
        """
        We have two different codepaths that
        extract a particular shape of dictionary
        for messages to send to clients:

            events:

                These are the events we send to MANY
                clients when a message is originally
                sent.

            fetch:

                These are the messages we send to ONE
                client when they fetch messages via
                some narrow/search in the UI.

        Different clients have different needs
        when it comes to things like generating avatar
        hashes or including both rendered and unrendered
        Markdown, so that explains the different shapes.

        And then the two codepaths have different
        performance needs.  In the events codepath, we
        have the Django view generate a single "wide"
        dictionary that gets put on the event queue,
        and then we send events to multiple clients,
        finalizing the payload for each of them depending
        on the "shape" they want.  (We also avoid
        doing extra work for any two clients who want
        the same shape dictionary, but that's out of the
        scope of this particular test).

        In the fetch scenario, the single client only needs
        a dictionary of one shape, but we need to re-hydrate
        the sender information, since the sender details
        may have changed since the message was originally
        sent.

        This test simply verifies that the two codepaths
        ultimately provide the same result.
        """

        def reload_message(msg_id: int) -> Message:
            # Get a clean copy of the message, and
            # clear the cache.
            cache_delete(to_dict_cache_key_id(msg_id))
            msg = Message.objects.get(id=msg_id)
            return msg

        def get_send_message_payload(
            msg_id: int, apply_markdown: bool, client_gravatar: bool
        ) -> Dict[str, Any]:
            msg = reload_message(msg_id)
            wide_dict = MessageDict.wide_dict(msg)

            narrow_dict = MessageDict.finalize_payload(
                wide_dict,
                apply_markdown=apply_markdown,
                client_gravatar=client_gravatar,
            )
            return narrow_dict

        def get_fetch_payload(
            msg_id: int, apply_markdown: bool, client_gravatar: bool
        ) -> Dict[str, Any]:
            msg = reload_message(msg_id)
            unhydrated_dict = MessageDict.to_dict_uncached_helper([msg])[0]
            # The next step mutates the dict in place
            # for performance reasons.
            MessageDict.post_process_dicts(
                [unhydrated_dict],
                apply_markdown=apply_markdown,
                client_gravatar=client_gravatar,
            )
            final_dict = unhydrated_dict
            return final_dict

        def test_message_id() -> int:
            hamlet = self.example_user("hamlet")
            self.login_user(hamlet)
            msg_id = self.send_stream_message(
                hamlet,
                "Denmark",
                topic_name="editing",
                content="before edit",
            )
            return msg_id

        flag_setups = [
            [False, False],
            [False, True],
            [True, False],
            [True, True],
        ]

        msg_id = test_message_id()

        for apply_markdown, client_gravatar in flag_setups:
            send_message_payload = get_send_message_payload(
                msg_id,
                apply_markdown=apply_markdown,
                client_gravatar=client_gravatar,
            )

            fetch_payload = get_fetch_payload(
                msg_id,
                apply_markdown=apply_markdown,
                client_gravatar=client_gravatar,
            )

            self.assertEqual(send_message_payload, fetch_payload)

    def test_bulk_message_fetching(self) -> None:
        sender = self.example_user("othello")
        receiver = self.example_user("hamlet")
        realm = get_realm("zulip")
        pm_recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        stream_name = "Çiğdem"
        stream = self.make_stream(stream_name)
        stream_recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        sending_client = make_client(name="test suite")

        ids = []
        for i in range(300):
            for recipient in [pm_recipient, stream_recipient]:
                message = Message(
                    sender=sender,
                    recipient=recipient,
                    realm=realm,
                    content=f"whatever {i}",
                    rendered_content="DOES NOT MATTER",
                    rendered_content_version=markdown_version,
                    date_sent=timezone_now(),
                    sending_client=sending_client,
                    last_edit_time=timezone_now(),
                    edit_history="[]",
                )
                message.set_topic_name("whatever")
                message.save()
                ids.append(message.id)

                Reaction.objects.create(
                    user_profile=sender, message=message, emoji_name="simple_smile"
                )

        num_ids = len(ids)
        self.assertTrue(num_ids >= 600)

        flush_per_request_caches()
        with self.assert_database_query_count(7):
            rows = list(MessageDict.get_raw_db_rows(ids))

            objs = [MessageDict.build_dict_from_raw_db_row(row) for row in rows]
            MessageDict.post_process_dicts(objs, apply_markdown=False, client_gravatar=False)

        self.assert_length(rows, num_ids)

    def test_applying_markdown(self) -> None:
        sender = self.example_user("othello")
        receiver = self.example_user("hamlet")
        recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        sending_client = make_client(name="test suite")
        message = Message(
            sender=sender,
            recipient=recipient,
            realm=receiver.realm,
            content="hello **world**",
            date_sent=timezone_now(),
            sending_client=sending_client,
            last_edit_time=timezone_now(),
            edit_history="[]",
        )
        message.set_topic_name("whatever")
        message.save()

        # An important part of this test is to get the message through this exact code path,
        # because there is an ugly hack we need to cover.  So don't just say "row = message".
        row = MessageDict.get_raw_db_rows([message.id])[0]
        dct = MessageDict.build_dict_from_raw_db_row(row)
        expected_content = "<p>hello <strong>world</strong></p>"
        self.assertEqual(dct["rendered_content"], expected_content)
        message = Message.objects.get(id=message.id)
        self.assertEqual(message.rendered_content, expected_content)
        self.assertEqual(message.rendered_content_version, markdown_version)

    @mock.patch("zerver.lib.message.markdown_convert")
    def test_applying_markdown_invalid_format(self, convert_mock: Any) -> None:
        # pretend the converter returned an invalid message without raising an exception
        convert_mock.return_value = None
        sender = self.example_user("othello")
        receiver = self.example_user("hamlet")
        recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        sending_client = make_client(name="test suite")
        message = Message(
            sender=sender,
            recipient=recipient,
            realm=receiver.realm,
            content="hello **world**",
            date_sent=timezone_now(),
            sending_client=sending_client,
            last_edit_time=timezone_now(),
            edit_history="[]",
        )
        message.set_topic_name("whatever")
        message.save()

        # An important part of this test is to get the message through this exact code path,
        # because there is an ugly hack we need to cover.  So don't just say "row = message".
        row = MessageDict.get_raw_db_rows([message.id])[0]
        dct = MessageDict.build_dict_from_raw_db_row(row)
        error_content = (
            "<p>[Zulip note: Sorry, we could not understand the formatting of your message]</p>"
        )
        self.assertEqual(dct["rendered_content"], error_content)

    def test_topic_links_use_stream_realm(self) -> None:
        # Set up a realm filter on 'zulip' and assert that messages
        # sent to a stream on 'zulip' have the topic linkified,
        # and not linkified when sent to a stream in 'lear'.
        zulip_realm = get_realm("zulip")
        lear_realm = get_realm("lear")
        url_format_string = r"https://trac.example.com/ticket/%(id)s"
        links = {"url": "https://trac.example.com/ticket/123", "text": "#123"}
        topic_name = "test #123"

        linkifier = RealmFilter(
            realm=zulip_realm, pattern=r"#(?P<id>[0-9]{2,8})", url_format_string=url_format_string
        )
        self.assertEqual(
            str(linkifier),
            "<RealmFilter(zulip): #(?P<id>[0-9]{2,8}) https://trac.example.com/ticket/%(id)s>",
        )

        def get_message(sender: UserProfile, realm: Realm) -> Message:
            stream_name = "Denmark"
            if not Stream.objects.filter(realm=realm, name=stream_name).exists():
                self.make_stream(stream_name, realm)
            self.subscribe(sender, stream_name)
            msg_id = self.send_stream_message(sender, "Denmark", "hello world", topic_name, realm)
            return Message.objects.get(id=msg_id)

        def assert_topic_links(links: List[Dict[str, str]], msg: Message) -> None:
            dct = MessageDict.to_dict_uncached_helper([msg])[0]
            self.assertEqual(dct[TOPIC_LINKS], links)

        # Send messages before and after saving the realm filter from each user.
        assert_topic_links([], get_message(self.example_user("othello"), zulip_realm))
        assert_topic_links([], get_message(self.lear_user("cordelia"), lear_realm))
        assert_topic_links([], get_message(self.notification_bot(zulip_realm), zulip_realm))
        linkifier.save()
        assert_topic_links([links], get_message(self.example_user("othello"), zulip_realm))
        assert_topic_links([], get_message(self.lear_user("cordelia"), lear_realm))
        assert_topic_links([links], get_message(self.notification_bot(zulip_realm), zulip_realm))

    def test_reaction(self) -> None:
        sender = self.example_user("othello")
        receiver = self.example_user("hamlet")
        recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        sending_client = make_client(name="test suite")
        message = Message(
            sender=sender,
            recipient=recipient,
            realm=receiver.realm,
            content="hello **world**",
            date_sent=timezone_now(),
            sending_client=sending_client,
            last_edit_time=timezone_now(),
            edit_history="[]",
        )
        message.set_topic_name("whatever")
        message.save()

        reaction = Reaction.objects.create(
            message=message, user_profile=sender, emoji_name="simple_smile"
        )
        row = MessageDict.get_raw_db_rows([message.id])[0]
        msg_dict = MessageDict.build_dict_from_raw_db_row(row)
        self.assertEqual(msg_dict["reactions"][0]["emoji_name"], reaction.emoji_name)
        self.assertEqual(msg_dict["reactions"][0]["user_id"], sender.id)
        self.assertEqual(msg_dict["reactions"][0]["user"]["id"], sender.id)
        self.assertEqual(msg_dict["reactions"][0]["user"]["email"], sender.email)
        self.assertEqual(msg_dict["reactions"][0]["user"]["full_name"], sender.full_name)

    def test_missing_anchor(self) -> None:
        self.login("hamlet")
        result = self.client_get(
            "/json/messages",
            {"use_first_unread_anchor": "false", "num_before": "1", "num_after": "1"},
        )

        self.assert_json_error(result, "Missing 'anchor' argument.")

    def test_invalid_anchor(self) -> None:
        self.login("hamlet")
        result = self.client_get(
            "/json/messages",
            {
                "use_first_unread_anchor": "false",
                "num_before": "1",
                "num_after": "1",
                "anchor": "chocolate",
            },
        )

        self.assert_json_error(result, "Invalid anchor")


class MessageHydrationTest(ZulipTestCase):
    def test_hydrate_stream_recipient_info(self) -> None:
        realm = get_realm("zulip")
        cordelia = self.example_user("cordelia")

        stream_id = get_stream("Verona", realm).id

        obj = dict(
            recipient_type=Recipient.STREAM,
            recipient_type_id=stream_id,
            sender_is_mirror_dummy=False,
            sender_email=cordelia.email,
            sender_full_name=cordelia.full_name,
            sender_id=cordelia.id,
        )

        MessageDict.hydrate_recipient_info(obj, "Verona")

        self.assertEqual(obj["display_recipient"], "Verona")
        self.assertEqual(obj["type"], "stream")

    def test_hydrate_pm_recipient_info(self) -> None:
        cordelia = self.example_user("cordelia")
        display_recipient: List[UserDisplayRecipient] = [
            dict(
                email="aaron@example.com",
                full_name="Aaron Smith",
                id=999,
                is_mirror_dummy=False,
            ),
        ]

        obj = dict(
            recipient_type=Recipient.PERSONAL,
            recipient_type_id=None,
            sender_is_mirror_dummy=False,
            sender_email=cordelia.email,
            sender_full_name=cordelia.full_name,
            sender_id=cordelia.id,
        )

        MessageDict.hydrate_recipient_info(obj, display_recipient)

        self.assertEqual(
            obj["display_recipient"],
            [
                dict(
                    email="aaron@example.com",
                    full_name="Aaron Smith",
                    id=999,
                    is_mirror_dummy=False,
                ),
                dict(
                    email=cordelia.email,
                    full_name=cordelia.full_name,
                    id=cordelia.id,
                    is_mirror_dummy=False,
                ),
            ],
        )
        self.assertEqual(obj["type"], "private")

    def test_messages_for_ids(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        stream_name = "test stream"
        self.subscribe(cordelia, stream_name)

        old_message_id = self.send_stream_message(cordelia, stream_name, content="foo")

        self.subscribe(hamlet, stream_name)

        content = "hello @**King Hamlet**"
        new_message_id = self.send_stream_message(cordelia, stream_name, content=content)

        user_message_flags = {
            old_message_id: ["read", "historical"],
            new_message_id: ["mentioned"],
        }

        messages = messages_for_ids(
            message_ids=[old_message_id, new_message_id],
            user_message_flags=user_message_flags,
            search_fields={},
            apply_markdown=True,
            client_gravatar=True,
            allow_edit_history=False,
        )

        self.assert_length(messages, 2)

        for message in messages:
            if message["id"] == old_message_id:
                old_message = message
            elif message["id"] == new_message_id:
                new_message = message

        self.assertEqual(old_message["content"], "<p>foo</p>")
        self.assertEqual(old_message["flags"], ["read", "historical"])

        self.assertIn('class="user-mention"', new_message["content"])
        self.assertEqual(new_message["flags"], ["mentioned"])

    def test_display_recipient_up_to_date(self) -> None:
        """
        This is a test for a bug where due to caching of message_dicts,
        after updating a user's information, fetching those cached messages
        via messages_for_ids would return message_dicts with display_recipient
        still having the old information. The returned message_dicts should have
        up-to-date display_recipients and we check for that here.
        """

        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        message_id = self.send_personal_message(hamlet, cordelia, "test")

        cordelia_recipient = cordelia.recipient
        # Cause the display_recipient to get cached:
        assert cordelia_recipient is not None
        get_display_recipient(cordelia_recipient)

        # Change cordelia's email:
        cordelia_new_email = "new-cordelia@zulip.com"
        cordelia.email = cordelia_new_email
        cordelia.save()

        # Local display_recipient cache needs to be flushed.
        # flush_per_request_caches() is called after every request,
        # so it makes sense to run it here.
        flush_per_request_caches()

        messages = messages_for_ids(
            message_ids=[message_id],
            user_message_flags={message_id: ["read"]},
            search_fields={},
            apply_markdown=True,
            client_gravatar=True,
            allow_edit_history=False,
        )
        message = messages[0]

        # Find which display_recipient in the list is cordelia:
        for display_recipient in message["display_recipient"]:
            if display_recipient["id"] == cordelia.id:
                cordelia_display_recipient = display_recipient

        # Make sure the email is up-to-date.
        self.assertEqual(cordelia_display_recipient["email"], cordelia_new_email)


class TestMessageForIdsDisplayRecipientFetching(ZulipTestCase):
    def _verify_display_recipient(
        self,
        display_recipient: DisplayRecipientT,
        expected_recipient_objects: Union[Stream, List[UserProfile]],
    ) -> None:
        if isinstance(expected_recipient_objects, Stream):
            self.assertEqual(display_recipient, expected_recipient_objects.name)

        else:
            for user_profile in expected_recipient_objects:
                recipient_dict: UserDisplayRecipient = {
                    "email": user_profile.email,
                    "full_name": user_profile.full_name,
                    "id": user_profile.id,
                    "is_mirror_dummy": user_profile.is_mirror_dummy,
                }
                self.assertTrue(recipient_dict in display_recipient)

    def test_display_recipient_personal(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        message_ids = [
            self.send_personal_message(hamlet, cordelia, "test"),
            self.send_personal_message(cordelia, othello, "test"),
        ]

        messages = messages_for_ids(
            message_ids=message_ids,
            user_message_flags={message_id: ["read"] for message_id in message_ids},
            search_fields={},
            apply_markdown=True,
            client_gravatar=True,
            allow_edit_history=False,
        )

        self._verify_display_recipient(messages[0]["display_recipient"], [hamlet, cordelia])
        self._verify_display_recipient(messages[1]["display_recipient"], [cordelia, othello])

    def test_display_recipient_stream(self) -> None:
        cordelia = self.example_user("cordelia")
        self.subscribe(cordelia, "Denmark")

        message_ids = [
            self.send_stream_message(cordelia, "Verona", content="test"),
            self.send_stream_message(cordelia, "Denmark", content="test"),
        ]

        messages = messages_for_ids(
            message_ids=message_ids,
            user_message_flags={message_id: ["read"] for message_id in message_ids},
            search_fields={},
            apply_markdown=True,
            client_gravatar=True,
            allow_edit_history=False,
        )

        self._verify_display_recipient(
            messages[0]["display_recipient"], get_stream("Verona", cordelia.realm)
        )
        self._verify_display_recipient(
            messages[1]["display_recipient"], get_stream("Denmark", cordelia.realm)
        )

    def test_display_recipient_huddle(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        iago = self.example_user("iago")
        message_ids = [
            self.send_huddle_message(hamlet, [cordelia, othello], "test"),
            self.send_huddle_message(cordelia, [hamlet, othello, iago], "test"),
        ]

        messages = messages_for_ids(
            message_ids=message_ids,
            user_message_flags={message_id: ["read"] for message_id in message_ids},
            search_fields={},
            apply_markdown=True,
            client_gravatar=True,
            allow_edit_history=False,
        )

        self._verify_display_recipient(
            messages[0]["display_recipient"], [hamlet, cordelia, othello]
        )
        self._verify_display_recipient(
            messages[1]["display_recipient"], [hamlet, cordelia, othello, iago]
        )

    def test_display_recipient_various_types(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        iago = self.example_user("iago")

        self.subscribe(cordelia, "Denmark")
        self.subscribe(hamlet, "Scotland")

        message_ids = [
            self.send_huddle_message(hamlet, [cordelia, othello], "test"),
            self.send_stream_message(cordelia, "Verona", content="test"),
            self.send_personal_message(hamlet, cordelia, "test"),
            self.send_stream_message(cordelia, "Denmark", content="test"),
            self.send_huddle_message(cordelia, [hamlet, othello, iago], "test"),
            self.send_personal_message(cordelia, othello, "test"),
        ]

        messages = messages_for_ids(
            message_ids=message_ids,
            user_message_flags={message_id: ["read"] for message_id in message_ids},
            search_fields={},
            apply_markdown=True,
            client_gravatar=True,
            allow_edit_history=False,
        )

        self._verify_display_recipient(
            messages[0]["display_recipient"], [hamlet, cordelia, othello]
        )
        self._verify_display_recipient(
            messages[1]["display_recipient"], get_stream("Verona", hamlet.realm)
        )
        self._verify_display_recipient(messages[2]["display_recipient"], [hamlet, cordelia])
        self._verify_display_recipient(
            messages[3]["display_recipient"], get_stream("Denmark", hamlet.realm)
        )
        self._verify_display_recipient(
            messages[4]["display_recipient"], [hamlet, cordelia, othello, iago]
        )
        self._verify_display_recipient(messages[5]["display_recipient"], [cordelia, othello])


class SewMessageAndReactionTest(ZulipTestCase):
    def test_sew_messages_and_reaction(self) -> None:
        sender = self.example_user("othello")
        receiver = self.example_user("hamlet")
        realm = get_realm("zulip")
        pm_recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        stream_name = "Çiğdem"
        stream = self.make_stream(stream_name)
        stream_recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        sending_client = make_client(name="test suite")

        needed_ids = []
        for i in range(5):
            for recipient in [pm_recipient, stream_recipient]:
                message = Message(
                    sender=sender,
                    recipient=recipient,
                    realm=realm,
                    content=f"whatever {i}",
                    date_sent=timezone_now(),
                    sending_client=sending_client,
                    last_edit_time=timezone_now(),
                    edit_history="[]",
                )
                message.set_topic_name("whatever")
                message.save()
                needed_ids.append(message.id)
                reaction = Reaction(user_profile=sender, message=message, emoji_name="simple_smile")
                reaction.save()

        messages = Message.objects.filter(id__in=needed_ids).values(*["id", "content"])
        reactions = Reaction.get_raw_db_rows(needed_ids)
        tied_data = sew_messages_and_reactions(messages, reactions)
        for data in tied_data:
            self.assert_length(data["reactions"], 1)
            self.assertEqual(data["reactions"][0]["emoji_name"], "simple_smile")
            self.assertTrue(data["id"])
            self.assertTrue(data["content"])
