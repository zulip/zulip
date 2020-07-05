import time
from typing import Any, Dict, List
from unittest import mock

from django.utils.timezone import now as timezone_now

from zerver.lib.cache import cache_delete, to_dict_cache_key_id
from zerver.lib.markdown import version as markdown_version
from zerver.lib.message import MessageDict
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import make_client, queries_captured
from zerver.lib.topic import TOPIC_LINKS
from zerver.models import (
    Message,
    Reaction,
    RealmFilter,
    Recipient,
    UserProfile,
    flush_per_request_caches,
    get_realm,
)


class MessageDictTest(ZulipTestCase):
    def test_both_codepaths(self) -> None:
        '''
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
        markdown, so that explains the different shapes.

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
        '''

        def reload_message(msg_id: int) -> Message:
            # Get a clean copy of the message, and
            # clear the cache.
            cache_delete(to_dict_cache_key_id(msg_id))
            msg = Message.objects.get(id=msg_id)
            return msg

        def get_send_message_payload(
                msg_id: int,
                apply_markdown: bool,
                client_gravatar: bool) -> Dict[str, Any]:
            msg = reload_message(msg_id)
            wide_dict = MessageDict.wide_dict(msg)

            narrow_dict = MessageDict.finalize_payload(
                wide_dict,
                apply_markdown=apply_markdown,
                client_gravatar=client_gravatar,
            )
            return narrow_dict

        def get_fetch_payload(
                msg_id: int,
                apply_markdown: bool,
                client_gravatar: bool) -> Dict[str, Any]:
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
            hamlet = self.example_user('hamlet')
            self.login_user(hamlet)
            msg_id = self.send_stream_message(
                hamlet,
                "Scotland",
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

        for (apply_markdown, client_gravatar) in flag_setups:
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
        sender = self.example_user('othello')
        receiver = self.example_user('hamlet')
        pm_recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        stream_name = 'Çiğdem'
        stream = self.make_stream(stream_name)
        stream_recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        sending_client = make_client(name="test suite")

        ids = []
        for i in range(300):
            for recipient in [pm_recipient, stream_recipient]:
                message = Message(
                    sender=sender,
                    recipient=recipient,
                    content=f'whatever {i}',
                    rendered_content='DOES NOT MATTER',
                    rendered_content_version=markdown_version,
                    date_sent=timezone_now(),
                    sending_client=sending_client,
                    last_edit_time=timezone_now(),
                    edit_history='[]',
                )
                message.set_topic_name('whatever')
                message.save()
                ids.append(message.id)

                Reaction.objects.create(user_profile=sender, message=message,
                                        emoji_name='simple_smile')

        num_ids = len(ids)
        self.assertTrue(num_ids >= 600)

        flush_per_request_caches()
        t = time.time()
        with queries_captured() as queries:
            rows = list(MessageDict.get_raw_db_rows(ids))

            objs = [
                MessageDict.build_dict_from_raw_db_row(row)
                for row in rows
            ]
            MessageDict.post_process_dicts(objs, apply_markdown=False, client_gravatar=False)

        delay = time.time() - t
        # Make sure we don't take longer than 1.5ms per message to
        # extract messages.  Note that we increased this from 1ms to
        # 1.5ms to handle tests running in parallel being a bit
        # slower.
        error_msg = f"Number of ids: {num_ids}. Time delay: {delay}"
        self.assertTrue(delay < 0.0015 * num_ids, error_msg)
        self.assert_length(queries, 7)
        self.assertEqual(len(rows), num_ids)

    def test_applying_markdown(self) -> None:
        sender = self.example_user('othello')
        receiver = self.example_user('hamlet')
        recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        sending_client = make_client(name="test suite")
        message = Message(
            sender=sender,
            recipient=recipient,
            content='hello **world**',
            date_sent=timezone_now(),
            sending_client=sending_client,
            last_edit_time=timezone_now(),
            edit_history='[]',
        )
        message.set_topic_name('whatever')
        message.save()

        # An important part of this test is to get the message through this exact code path,
        # because there is an ugly hack we need to cover.  So don't just say "row = message".
        row = MessageDict.get_raw_db_rows([message.id])[0]
        dct = MessageDict.build_dict_from_raw_db_row(row)
        expected_content = '<p>hello <strong>world</strong></p>'
        self.assertEqual(dct['rendered_content'], expected_content)
        message = Message.objects.get(id=message.id)
        self.assertEqual(message.rendered_content, expected_content)
        self.assertEqual(message.rendered_content_version, markdown_version)

    @mock.patch("zerver.lib.message.markdown_convert")
    def test_applying_markdown_invalid_format(self, convert_mock: Any) -> None:
        # pretend the converter returned an invalid message without raising an exception
        convert_mock.return_value = None
        sender = self.example_user('othello')
        receiver = self.example_user('hamlet')
        recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        sending_client = make_client(name="test suite")
        message = Message(
            sender=sender,
            recipient=recipient,
            content='hello **world**',
            date_sent=timezone_now(),
            sending_client=sending_client,
            last_edit_time=timezone_now(),
            edit_history='[]',
        )
        message.set_topic_name('whatever')
        message.save()

        # An important part of this test is to get the message through this exact code path,
        # because there is an ugly hack we need to cover.  So don't just say "row = message".
        row = MessageDict.get_raw_db_rows([message.id])[0]
        dct = MessageDict.build_dict_from_raw_db_row(row)
        error_content = '<p>[Zulip note: Sorry, we could not understand the formatting of your message]</p>'
        self.assertEqual(dct['rendered_content'], error_content)

    def test_topic_links_use_stream_realm(self) -> None:
        # Set up a realm filter on 'zulip' and assert that messages
        # sent to a stream on 'zulip' have the topic linkified from
        # senders in both the 'zulip' and 'lear' realms as well as
        # the notification bot.
        zulip_realm = get_realm('zulip')
        url_format_string = r"https://trac.example.com/ticket/%(id)s"
        url = 'https://trac.example.com/ticket/123'
        topic_name = 'test #123'

        realm_filter = RealmFilter(realm=zulip_realm,
                                   pattern=r"#(?P<id>[0-9]{2,8})",
                                   url_format_string=url_format_string)
        self.assertEqual(
            realm_filter.__str__(),
            '<RealmFilter(zulip): #(?P<id>[0-9]{2,8})'
            ' https://trac.example.com/ticket/%(id)s>')

        def get_message(sender: UserProfile) -> Message:
            msg_id = self.send_stream_message(sender, 'Denmark', 'hello world', topic_name,
                                              zulip_realm)
            return Message.objects.get(id=msg_id)

        def assert_topic_links(links: List[str], msg: Message) -> None:
            dct = MessageDict.to_dict_uncached_helper([msg])[0]
            self.assertEqual(dct[TOPIC_LINKS], links)

        # Send messages before and after saving the realm filter from each user.
        assert_topic_links([], get_message(self.example_user('othello')))
        assert_topic_links([], get_message(self.lear_user('cordelia')))
        assert_topic_links([], get_message(self.notification_bot()))
        realm_filter.save()
        assert_topic_links([url], get_message(self.example_user('othello')))
        assert_topic_links([url], get_message(self.lear_user('cordelia')))
        assert_topic_links([url], get_message(self.notification_bot()))

    def test_reaction(self) -> None:
        sender = self.example_user('othello')
        receiver = self.example_user('hamlet')
        recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        sending_client = make_client(name="test suite")
        message = Message(
            sender=sender,
            recipient=recipient,
            content='hello **world**',
            date_sent=timezone_now(),
            sending_client=sending_client,
            last_edit_time=timezone_now(),
            edit_history='[]',
        )
        message.set_topic_name('whatever')
        message.save()

        reaction = Reaction.objects.create(
            message=message, user_profile=sender,
            emoji_name='simple_smile')
        row = MessageDict.get_raw_db_rows([message.id])[0]
        msg_dict = MessageDict.build_dict_from_raw_db_row(row)
        self.assertEqual(msg_dict['reactions'][0]['emoji_name'],
                         reaction.emoji_name)
        self.assertEqual(msg_dict['reactions'][0]['user_id'], sender.id)
        self.assertEqual(msg_dict['reactions'][0]['user']['id'],
                         sender.id)
        self.assertEqual(msg_dict['reactions'][0]['user']['email'],
                         sender.email)
        self.assertEqual(msg_dict['reactions'][0]['user']['full_name'],
                         sender.full_name)

    def test_missing_anchor(self) -> None:
        self.login('hamlet')
        result = self.client_get(
            '/json/messages?use_first_unread_anchor=false&num_before=1&num_after=1')

        self.assert_json_error(
            result, "Missing 'anchor' argument.")

    def test_invalid_anchor(self) -> None:
        self.login('hamlet')
        result = self.client_get(
            '/json/messages?use_first_unread_anchor=false&num_before=1&num_after=1&anchor=chocolate')

        self.assert_json_error(
            result, "Invalid anchor")
