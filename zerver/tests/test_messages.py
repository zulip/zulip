import datetime
from typing import Any, Dict, List
from unittest import mock

import ujson
from django.http import HttpResponse
from django.utils.timezone import now as timezone_now

from analytics.lib.counts import COUNT_STATS
from analytics.models import RealmCount
from zerver.decorator import JsonableError
from zerver.lib.actions import (
    check_message,
    do_change_stream_invite_only,
    do_claim_attachments,
    do_create_user,
    do_update_message,
    gather_subscriptions_helper,
    get_active_presence_idle_user_ids,
    get_client,
    get_last_message_id,
    send_rate_limited_pm_notification_to_bot_owner,
)
from zerver.lib.addressee import Addressee
from zerver.lib.markdown import MentionData
from zerver.lib.message import (
    bulk_access_messages,
    get_first_visible_message_id,
    maybe_update_first_visible_message_id,
    render_markdown,
    sew_messages_and_reactions,
    update_first_visible_message_id,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    make_client,
    message_stream_count,
    most_recent_message,
    most_recent_usermessage,
)
from zerver.lib.topic import DB_TOPIC_NAME
from zerver.lib.upload import create_attachment
from zerver.lib.url_encoding import near_message_url
from zerver.models import (
    Attachment,
    Message,
    Reaction,
    Recipient,
    Subscription,
    UserMessage,
    UserPresence,
    UserProfile,
    bulk_get_huddle_user_ids,
    get_huddle_user_ids,
    get_realm,
    get_stream,
)


class MiscMessageTest(ZulipTestCase):
    def test_get_last_message_id(self) -> None:
        self.assertEqual(
            get_last_message_id(),
            Message.objects.latest('id').id,
        )

        Message.objects.all().delete()

        self.assertEqual(get_last_message_id(), -1)

class TestAddressee(ZulipTestCase):
    def test_addressee_for_user_ids(self) -> None:
        realm = get_realm('zulip')
        user_ids = [self.example_user('cordelia').id,
                    self.example_user('hamlet').id,
                    self.example_user('othello').id]

        result = Addressee.for_user_ids(user_ids=user_ids, realm=realm)
        user_profiles = result.user_profiles()
        result_user_ids = [user_profiles[0].id, user_profiles[1].id,
                           user_profiles[2].id]

        self.assertEqual(set(result_user_ids), set(user_ids))

    def test_addressee_for_user_ids_nonexistent_id(self) -> None:
        def assert_invalid_user_id() -> Any:
            return self.assertRaisesRegex(
                JsonableError,
                'Invalid user ID ')

        with assert_invalid_user_id():
            Addressee.for_user_ids(user_ids=[779], realm=get_realm('zulip'))

    def test_addressee_legacy_build_for_user_ids(self) -> None:
        realm = get_realm('zulip')
        self.login('hamlet')
        user_ids = [self.example_user('cordelia').id,
                    self.example_user('othello').id]

        result = Addressee.legacy_build(
            sender=self.example_user('hamlet'), message_type_name='private',
            message_to=user_ids, topic_name='random_topic',
            realm=realm,
        )
        user_profiles = result.user_profiles()
        result_user_ids = [user_profiles[0].id, user_profiles[1].id]

        self.assertEqual(set(result_user_ids), set(user_ids))

    def test_addressee_legacy_build_for_stream_id(self) -> None:
        realm = get_realm('zulip')
        self.login('iago')
        sender = self.example_user('iago')
        self.subscribe(sender, "Denmark")
        stream = get_stream('Denmark', realm)

        result = Addressee.legacy_build(
            sender=sender, message_type_name='stream',
            message_to=[stream.id], topic_name='random_topic',
            realm=realm,
        )

        stream_id = result.stream_id()
        self.assertEqual(stream.id, stream_id)

class PersonalMessagesTest(ZulipTestCase):

    def test_near_pm_message_url(self) -> None:
        realm = get_realm('zulip')
        message = dict(
            type='personal',
            id=555,
            display_recipient=[
                dict(id=77),
                dict(id=80),
            ],
        )
        url = near_message_url(
            realm=realm,
            message=message,
        )
        self.assertEqual(url, 'http://zulip.testserver/#narrow/pm-with/77,80-pm/near/555')

    def test_is_private_flag_not_leaked(self) -> None:
        """
        Make sure `is_private` flag is not leaked to the API.
        """
        self.login('hamlet')
        self.send_personal_message(self.example_user("hamlet"),
                                   self.example_user("cordelia"),
                                   "test")

        for msg in self.get_messages():
            self.assertNotIn('is_private', msg['flags'])

    def test_auto_subbed_to_personals(self) -> None:
        """
        Newly created users are auto-subbed to the ability to receive
        personals.
        """
        test_email = self.nonreg_email('test')
        self.register(test_email, "test")
        user_profile = self.nonreg_user('test')
        old_messages_count = message_stream_count(user_profile)
        self.send_personal_message(user_profile, user_profile)
        new_messages_count = message_stream_count(user_profile)
        self.assertEqual(new_messages_count, old_messages_count + 1)

        recipient = Recipient.objects.get(type_id=user_profile.id,
                                          type=Recipient.PERSONAL)
        message = most_recent_message(user_profile)
        self.assertEqual(message.recipient, recipient)

        with mock.patch('zerver.models.get_display_recipient', return_value='recip'):
            self.assertEqual(
                str(message),
                '<Message: recip /  / '
                '<UserProfile: {} {}>>'.format(user_profile.email, user_profile.realm))

            user_message = most_recent_usermessage(user_profile)
            self.assertEqual(
                str(user_message),
                f'<UserMessage: recip / {user_profile.email} ([])>',
            )

class SewMessageAndReactionTest(ZulipTestCase):
    def test_sew_messages_and_reaction(self) -> None:
        sender = self.example_user('othello')
        receiver = self.example_user('hamlet')
        pm_recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        stream_name = 'Çiğdem'
        stream = self.make_stream(stream_name)
        stream_recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        sending_client = make_client(name="test suite")

        needed_ids = []
        for i in range(5):
            for recipient in [pm_recipient, stream_recipient]:
                message = Message(
                    sender=sender,
                    recipient=recipient,
                    content=f'whatever {i}',
                    date_sent=timezone_now(),
                    sending_client=sending_client,
                    last_edit_time=timezone_now(),
                    edit_history='[]',
                )
                message.set_topic_name('whatever')
                message.save()
                needed_ids.append(message.id)
                reaction = Reaction(user_profile=sender, message=message,
                                    emoji_name='simple_smile')
                reaction.save()

        messages = Message.objects.filter(id__in=needed_ids).values(
            *['id', 'content'])
        reactions = Reaction.get_raw_db_rows(needed_ids)
        tied_data = sew_messages_and_reactions(messages, reactions)
        for data in tied_data:
            self.assertEqual(len(data['reactions']), 1)
            self.assertEqual(data['reactions'][0]['emoji_name'],
                             'simple_smile')
            self.assertTrue(data['id'])
            self.assertTrue(data['content'])

class MessageAccessTests(ZulipTestCase):
    def test_update_invalid_flags(self) -> None:
        message = self.send_personal_message(
            self.example_user("cordelia"),
            self.example_user("hamlet"),
            "hello",
        )

        self.login('hamlet')
        result = self.client_post("/json/messages/flags",
                                  {"messages": ujson.dumps([message]),
                                   "op": "add",
                                   "flag": "invalid"})
        self.assert_json_error(result, "Invalid flag: 'invalid'")

        result = self.client_post("/json/messages/flags",
                                  {"messages": ujson.dumps([message]),
                                   "op": "add",
                                   "flag": "is_private"})
        self.assert_json_error(result, "Invalid flag: 'is_private'")

        result = self.client_post("/json/messages/flags",
                                  {"messages": ujson.dumps([message]),
                                   "op": "add",
                                   "flag": "active_mobile_push_notification"})
        self.assert_json_error(result, "Invalid flag: 'active_mobile_push_notification'")

        result = self.client_post("/json/messages/flags",
                                  {"messages": ujson.dumps([message]),
                                   "op": "add",
                                   "flag": "mentioned"})
        self.assert_json_error(result, "Flag not editable: 'mentioned'")

    def change_star(self, messages: List[int], add: bool=True, **kwargs: Any) -> HttpResponse:
        return self.client_post("/json/messages/flags",
                                {"messages": ujson.dumps(messages),
                                 "op": "add" if add else "remove",
                                 "flag": "starred"},
                                **kwargs)

    def test_change_star(self) -> None:
        """
        You can set a message as starred/un-starred through
        POST /json/messages/flags.
        """
        self.login('hamlet')
        message_ids = [self.send_personal_message(self.example_user("hamlet"),
                                                  self.example_user("hamlet"),
                                                  "test")]

        # Star a message.
        result = self.change_star(message_ids)
        self.assert_json_success(result)

        for msg in self.get_messages():
            if msg['id'] in message_ids:
                self.assertEqual(msg['flags'], ['starred'])
            else:
                self.assertEqual(msg['flags'], ['read'])

        result = self.change_star(message_ids, False)
        self.assert_json_success(result)

        # Remove the stars.
        for msg in self.get_messages():
            if msg['id'] in message_ids:
                self.assertEqual(msg['flags'], [])

    def test_change_star_public_stream_historical(self) -> None:
        """
        You can set a message as starred/un-starred through
        POST /json/messages/flags.
        """
        stream_name = "new_stream"
        self.subscribe(self.example_user("hamlet"), stream_name)
        self.login('hamlet')
        message_ids = [
            self.send_stream_message(self.example_user("hamlet"), stream_name, "test"),
        ]
        # Send a second message so we can verify it isn't modified
        other_message_ids = [
            self.send_stream_message(self.example_user("hamlet"), stream_name, "test_unused"),
        ]
        received_message_ids = [
            self.send_personal_message(
                self.example_user("hamlet"),
                self.example_user("cordelia"),
                "test_received",
            ),
        ]

        # Now login as another user who wasn't on that stream
        self.login('cordelia')
        # Send a message to yourself to make sure we have at least one with the read flag
        sent_message_ids = [
            self.send_personal_message(
                self.example_user("cordelia"),
                self.example_user("cordelia"),
                "test_read_message",
            ),
        ]
        result = self.client_post("/json/messages/flags",
                                  {"messages": ujson.dumps(sent_message_ids),
                                   "op": "add",
                                   "flag": "read"})

        # We can't change flags other than "starred" on historical messages:
        result = self.client_post("/json/messages/flags",
                                  {"messages": ujson.dumps(message_ids),
                                   "op": "add",
                                   "flag": "read"})
        self.assert_json_error(result, 'Invalid message(s)')

        # Trying to change a list of more than one historical message fails
        result = self.change_star(message_ids * 2)
        self.assert_json_error(result, 'Invalid message(s)')

        # Confirm that one can change the historical flag now
        result = self.change_star(message_ids)
        self.assert_json_success(result)

        for msg in self.get_messages():
            if msg['id'] in message_ids:
                self.assertEqual(set(msg['flags']), {'starred', 'historical', 'read'})
            elif msg['id'] in received_message_ids:
                self.assertEqual(msg['flags'], [])
            else:
                self.assertEqual(msg['flags'], ['read'])
            self.assertNotIn(msg['id'], other_message_ids)

        result = self.change_star(message_ids, False)
        self.assert_json_success(result)

        # But it still doesn't work if you're in another realm
        user = self.mit_user('sipbtest')
        self.login_user(user)
        result = self.change_star(message_ids, subdomain="zephyr")
        self.assert_json_error(result, 'Invalid message(s)')

    def test_change_star_private_message_security(self) -> None:
        """
        You can set a message as starred/un-starred through
        POST /json/messages/flags.
        """
        self.login('hamlet')
        message_ids = [
            self.send_personal_message(
                self.example_user("hamlet"),
                self.example_user("hamlet"),
                "test",
            ),
        ]

        # Starring private messages you didn't receive fails.
        self.login('cordelia')
        result = self.change_star(message_ids)
        self.assert_json_error(result, 'Invalid message(s)')

    def test_change_star_private_stream_security(self) -> None:
        stream_name = "private_stream"
        self.make_stream(stream_name, invite_only=True)
        self.subscribe(self.example_user("hamlet"), stream_name)
        self.login('hamlet')
        message_ids = [
            self.send_stream_message(self.example_user("hamlet"), stream_name, "test"),
        ]

        # Starring private stream messages you received works
        result = self.change_star(message_ids)
        self.assert_json_success(result)

        # Starring private stream messages you didn't receive fails.
        self.login('cordelia')
        result = self.change_star(message_ids)
        self.assert_json_error(result, 'Invalid message(s)')

        stream_name = "private_stream_2"
        self.make_stream(stream_name, invite_only=True,
                         history_public_to_subscribers=True)
        self.subscribe(self.example_user("hamlet"), stream_name)
        self.login('hamlet')
        message_ids = [
            self.send_stream_message(self.example_user("hamlet"), stream_name, "test"),
        ]

        # With stream.history_public_to_subscribers = True, you still
        # can't see it if you didn't receive the message and are
        # not subscribed.
        self.login('cordelia')
        result = self.change_star(message_ids)
        self.assert_json_error(result, 'Invalid message(s)')

        # But if you subscribe, then you can star the message
        self.subscribe(self.example_user("cordelia"), stream_name)
        result = self.change_star(message_ids)
        self.assert_json_success(result)

    def test_new_message(self) -> None:
        """
        New messages aren't starred.
        """
        sender = self.example_user('hamlet')
        self.login_user(sender)
        content = "Test message for star"
        self.send_stream_message(sender, "Verona",
                                 content=content)

        sent_message = UserMessage.objects.filter(
            user_profile=self.example_user('hamlet'),
        ).order_by("id").reverse()[0]
        self.assertEqual(sent_message.message.content, content)
        self.assertFalse(sent_message.flags.starred)

    def test_change_star_public_stream_security_for_guest_user(self) -> None:
        # Guest user can't access(star) unsubscribed public stream messages
        normal_user = self.example_user("hamlet")
        stream_name = "public_stream"
        self.make_stream(stream_name)
        self.subscribe(normal_user, stream_name)
        self.login_user(normal_user)

        message_id = [
            self.send_stream_message(normal_user, stream_name, "test 1"),
        ]

        guest_user = self.example_user('polonius')
        self.login_user(guest_user)
        result = self.change_star(message_id)
        self.assert_json_error(result, 'Invalid message(s)')

        # Subscribed guest users can access public stream messages sent before they join
        self.subscribe(guest_user, stream_name)
        result = self.change_star(message_id)
        self.assert_json_success(result)

        # And messages sent after they join
        self.login_user(normal_user)
        message_id = [
            self.send_stream_message(normal_user, stream_name, "test 2"),
        ]
        self.login_user(guest_user)
        result = self.change_star(message_id)
        self.assert_json_success(result)

    def test_change_star_private_stream_security_for_guest_user(self) -> None:
        # Guest users can't access(star) unsubscribed private stream messages
        normal_user = self.example_user("hamlet")
        stream_name = "private_stream"
        stream = self.make_stream(stream_name, invite_only=True)
        self.subscribe(normal_user, stream_name)
        self.login_user(normal_user)

        message_id = [
            self.send_stream_message(normal_user, stream_name, "test 1"),
        ]

        guest_user = self.example_user('polonius')
        self.login_user(guest_user)
        result = self.change_star(message_id)
        self.assert_json_error(result, 'Invalid message(s)')

        # Guest user can't access messages of subscribed private streams if
        # history is not public to subscribers
        self.subscribe(guest_user, stream_name)
        result = self.change_star(message_id)
        self.assert_json_error(result, 'Invalid message(s)')

        # Guest user can access messages of subscribed private streams if
        # history is public to subscribers
        do_change_stream_invite_only(stream, True, history_public_to_subscribers=True)
        result = self.change_star(message_id)
        self.assert_json_success(result)

        # With history not public to subscribers, they can still see new messages
        do_change_stream_invite_only(stream, True, history_public_to_subscribers=False)
        self.login_user(normal_user)
        message_id = [
            self.send_stream_message(normal_user, stream_name, "test 2"),
        ]
        self.login_user(guest_user)
        result = self.change_star(message_id)
        self.assert_json_success(result)

    def test_bulk_access_messages_private_stream(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        stream_name = "private_stream"
        stream = self.make_stream(stream_name, invite_only=True,
                                  history_public_to_subscribers=False)

        self.subscribe(user, stream_name)
        # Send a message before subscribing a new user to stream
        message_one_id = self.send_stream_message(user,
                                                  stream_name, "Message one")

        later_subscribed_user = self.example_user("cordelia")
        # Subscribe a user to private-protected history stream
        self.subscribe(later_subscribed_user, stream_name)

        # Send a message after subscribing a new user to stream
        message_two_id = self.send_stream_message(user,
                                                  stream_name, "Message two")

        message_ids = [message_one_id, message_two_id]
        messages = [Message.objects.select_related().get(id=message_id)
                    for message_id in message_ids]

        filtered_messages = bulk_access_messages(later_subscribed_user, messages)

        # Message sent before subscribing wouldn't be accessible by later
        # subscribed user as stream has protected history
        self.assertEqual(len(filtered_messages), 1)
        self.assertEqual(filtered_messages[0].id, message_two_id)

        do_change_stream_invite_only(stream, True, history_public_to_subscribers=True)

        filtered_messages = bulk_access_messages(later_subscribed_user, messages)

        # Message sent before subscribing are accessible by 8user as stream
        # don't have protected history
        self.assertEqual(len(filtered_messages), 2)

        # Testing messages accessiblity for an unsubscribed user
        unsubscribed_user = self.example_user("ZOE")

        filtered_messages = bulk_access_messages(unsubscribed_user, messages)

        self.assertEqual(len(filtered_messages), 0)

    def test_bulk_access_messages_public_stream(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        # Testing messages accessiblity including a public stream message
        stream_name = "public_stream"
        self.subscribe(user, stream_name)
        message_one_id = self.send_stream_message(user,
                                                  stream_name, "Message one")

        later_subscribed_user = self.example_user("cordelia")
        self.subscribe(later_subscribed_user, stream_name)

        # Send a message after subscribing a new user to stream
        message_two_id = self.send_stream_message(user,
                                                  stream_name, "Message two")

        message_ids = [message_one_id, message_two_id]
        messages = [Message.objects.select_related().get(id=message_id)
                    for message_id in message_ids]

        # All public stream messages are always accessible
        filtered_messages = bulk_access_messages(later_subscribed_user, messages)
        self.assertEqual(len(filtered_messages), 2)

        unsubscribed_user = self.example_user("ZOE")
        filtered_messages = bulk_access_messages(unsubscribed_user, messages)

        self.assertEqual(len(filtered_messages), 2)

class MessageHasKeywordsTest(ZulipTestCase):
    '''Test for keywords like has_link, has_image, has_attachment.'''

    def setup_dummy_attachments(self, user_profile: UserProfile) -> List[str]:
        sample_size = 10
        realm_id = user_profile.realm_id
        dummy_files = [
            ('zulip.txt', f'{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt', sample_size),
            ('temp_file.py', f'{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py', sample_size),
            ('abc.py', f'{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py', sample_size),
        ]

        for file_name, path_id, size in dummy_files:
            create_attachment(file_name, path_id, user_profile, size)

        # return path ids
        return [x[1] for x in dummy_files]

    def test_claim_attachment(self) -> None:
        user_profile = self.example_user('hamlet')
        dummy_path_ids = self.setup_dummy_attachments(user_profile)
        dummy_urls = [f"http://zulip.testserver/user_uploads/{x}" for x in dummy_path_ids]

        # Send message referring the attachment
        self.subscribe(user_profile, "Denmark")

        def assert_attachment_claimed(path_id: str, claimed: bool) -> None:
            attachment = Attachment.objects.get(path_id=path_id)
            self.assertEqual(attachment.is_claimed(), claimed)

        # This message should claim attachments 1 only because attachment 2
        # is not being parsed as a link by Markdown.
        body = ("Some files here ...[zulip.txt]({})" +
                "{}.... Some more...." +
                "{}").format(dummy_urls[0], dummy_urls[1], dummy_urls[1])
        self.send_stream_message(user_profile, "Denmark", body, "test")
        assert_attachment_claimed(dummy_path_ids[0], True)
        assert_attachment_claimed(dummy_path_ids[1], False)

        # This message tries to claim the third attachment but fails because
        # Markdown would not set has_attachments = True here.
        body = f"Link in code: `{dummy_urls[2]}`"
        self.send_stream_message(user_profile, "Denmark", body, "test")
        assert_attachment_claimed(dummy_path_ids[2], False)

        # Another scenario where we wouldn't parse the link.
        body = f"Link to not parse: .{dummy_urls[2]}.`"
        self.send_stream_message(user_profile, "Denmark", body, "test")
        assert_attachment_claimed(dummy_path_ids[2], False)

        # Finally, claim attachment 3.
        body = f"Link: {dummy_urls[2]}"
        self.send_stream_message(user_profile, "Denmark", body, "test")
        assert_attachment_claimed(dummy_path_ids[2], True)
        assert_attachment_claimed(dummy_path_ids[1], False)

    def test_finds_all_links(self) -> None:
        msg_ids = []
        msg_contents = ["foo.org", "[bar](baz.gov)", "http://quux.ca"]
        for msg_content in msg_contents:
            msg_ids.append(self.send_stream_message(self.example_user('hamlet'),
                                                    'Denmark', content=msg_content))
        msgs = [Message.objects.get(id=id) for id in msg_ids]
        self.assertTrue(all([msg.has_link for msg in msgs]))

    def test_finds_only_links(self) -> None:
        msg_ids = []
        msg_contents = ["`example.org`", '``example.org```', '$$https://example.org$$', "foo"]
        for msg_content in msg_contents:
            msg_ids.append(self.send_stream_message(self.example_user('hamlet'),
                                                    'Denmark', content=msg_content))
        msgs = [Message.objects.get(id=id) for id in msg_ids]
        self.assertFalse(all([msg.has_link for msg in msgs]))

    def update_message(self, msg: Message, content: str) -> None:
        hamlet = self.example_user('hamlet')
        realm_id = hamlet.realm.id
        rendered_content = render_markdown(msg, content)
        mention_data = MentionData(realm_id, content)
        do_update_message(hamlet, msg, None, None, "change_one", False, False, content,
                          rendered_content, set(), set(), mention_data=mention_data)

    def test_finds_link_after_edit(self) -> None:
        hamlet = self.example_user('hamlet')
        msg_id = self.send_stream_message(hamlet, 'Denmark', content='a')
        msg = Message.objects.get(id=msg_id)

        self.assertFalse(msg.has_link)
        self.update_message(msg, 'a http://foo.com')
        self.assertTrue(msg.has_link)
        self.update_message(msg, 'a')
        self.assertFalse(msg.has_link)
        # Check in blockquotes work
        self.update_message(msg, '> http://bar.com')
        self.assertTrue(msg.has_link)
        self.update_message(msg, 'a `http://foo.com`')
        self.assertFalse(msg.has_link)

    def test_has_image(self) -> None:
        msg_ids = []
        msg_contents = ["Link: foo.org",
                        "Image: https://www.google.com/images/srpr/logo4w.png",
                        "Image: https://www.google.com/images/srpr/logo4w.pdf",
                        "[Google Link](https://www.google.com/images/srpr/logo4w.png)"]
        for msg_content in msg_contents:
            msg_ids.append(self.send_stream_message(self.example_user('hamlet'),
                                                    'Denmark', content=msg_content))
        msgs = [Message.objects.get(id=id) for id in msg_ids]
        self.assertEqual([False, True, False, True], [msg.has_image for msg in msgs])

        self.update_message(msgs[0], 'https://www.google.com/images/srpr/logo4w.png')
        self.assertTrue(msgs[0].has_image)
        self.update_message(msgs[0], 'No Image Again')
        self.assertFalse(msgs[0].has_image)

    def test_has_attachment(self) -> None:
        hamlet = self.example_user('hamlet')
        dummy_path_ids = self.setup_dummy_attachments(hamlet)
        dummy_urls = [f"http://zulip.testserver/user_uploads/{x}" for x in dummy_path_ids]
        self.subscribe(hamlet, "Denmark")

        body = ("Files ...[zulip.txt]({}) {} {}").format(dummy_urls[0], dummy_urls[1], dummy_urls[2])

        msg_id = self.send_stream_message(hamlet, "Denmark", body, "test")
        msg = Message.objects.get(id=msg_id)
        self.assertTrue(msg.has_attachment)
        self.update_message(msg, 'No Attachments')
        self.assertFalse(msg.has_attachment)
        self.update_message(msg, body)
        self.assertTrue(msg.has_attachment)
        self.update_message(msg, f'Link in code: `{dummy_urls[1]}`')
        self.assertFalse(msg.has_attachment)
        # Test blockquotes
        self.update_message(msg, f'> {dummy_urls[1]}')
        self.assertTrue(msg.has_attachment)

        # Additional test to check has_attachment is being set is due to the correct attachment.
        self.update_message(msg, f'Outside: {dummy_urls[0]}. In code: `{dummy_urls[1]}`.')
        self.assertTrue(msg.has_attachment)
        self.assertTrue(msg.attachment_set.filter(path_id=dummy_path_ids[0]))
        self.assertEqual(msg.attachment_set.count(), 1)

        self.update_message(msg, f'Outside: {dummy_urls[1]}. In code: `{dummy_urls[0]}`.')
        self.assertTrue(msg.has_attachment)
        self.assertTrue(msg.attachment_set.filter(path_id=dummy_path_ids[1]))
        self.assertEqual(msg.attachment_set.count(), 1)

        self.update_message(msg, f'Both in code: `{dummy_urls[1]} {dummy_urls[0]}`.')
        self.assertFalse(msg.has_attachment)
        self.assertEqual(msg.attachment_set.count(), 0)

    def test_potential_attachment_path_ids(self) -> None:
        hamlet = self.example_user('hamlet')
        self.subscribe(hamlet, "Denmark")
        dummy_path_ids = self.setup_dummy_attachments(hamlet)

        body = "Hello"
        msg_id = self.send_stream_message(hamlet, "Denmark", body, "test")
        msg = Message.objects.get(id=msg_id)

        with mock.patch("zerver.lib.actions.do_claim_attachments",
                        wraps=do_claim_attachments) as m:
            self.update_message(msg, f'[link](http://{hamlet.realm.host}/user_uploads/{dummy_path_ids[0]})')
            self.assertTrue(m.called)
            m.reset_mock()

            self.update_message(msg, f'[link](/user_uploads/{dummy_path_ids[1]})')
            self.assertTrue(m.called)
            m.reset_mock()

            self.update_message(msg, f'[new text link](/user_uploads/{dummy_path_ids[1]})')
            self.assertFalse(m.called)
            m.reset_mock()

            # It's not clear this is correct behavior
            self.update_message(msg, f'[link](user_uploads/{dummy_path_ids[2]})')
            self.assertFalse(m.called)
            m.reset_mock()

            self.update_message(msg, f'[link](https://github.com/user_uploads/{dummy_path_ids[0]})')
            self.assertFalse(m.called)
            m.reset_mock()

class MissedMessageTest(ZulipTestCase):
    def test_presence_idle_user_ids(self) -> None:
        UserPresence.objects.all().delete()

        sender = self.example_user('cordelia')
        realm = sender.realm
        hamlet = self.example_user('hamlet')
        othello = self.example_user('othello')
        recipient_ids = {hamlet.id, othello.id}
        message_type = 'stream'
        user_flags: Dict[int, List[str]] = {}

        def assert_missing(user_ids: List[int]) -> None:
            presence_idle_user_ids = get_active_presence_idle_user_ids(
                realm=realm,
                sender_id=sender.id,
                message_type=message_type,
                active_user_ids=recipient_ids,
                user_flags=user_flags,
            )
            self.assertEqual(sorted(user_ids), sorted(presence_idle_user_ids))

        def set_presence(user: UserProfile, client_name: str, ago: int) -> None:
            when = timezone_now() - datetime.timedelta(seconds=ago)
            UserPresence.objects.create(
                user_profile_id=user.id,
                realm_id=user.realm_id,
                client=get_client(client_name),
                timestamp=when,
            )

        message_type = 'private'
        assert_missing([hamlet.id, othello.id])

        message_type = 'stream'
        user_flags[hamlet.id] = ['mentioned']
        assert_missing([hamlet.id])

        set_presence(hamlet, 'iPhone', ago=5000)
        assert_missing([hamlet.id])

        set_presence(hamlet, 'webapp', ago=15)
        assert_missing([])

        message_type = 'private'
        assert_missing([othello.id])

class LogDictTest(ZulipTestCase):
    def test_to_log_dict(self) -> None:
        user = self.example_user('hamlet')
        stream_name = 'Denmark'
        topic_name = 'Copenhagen'
        content = 'find me some good coffee shops'
        message_id = self.send_stream_message(user, stream_name,
                                              topic_name=topic_name,
                                              content=content)
        message = Message.objects.get(id=message_id)
        dct = message.to_log_dict()

        self.assertTrue('timestamp' in dct)

        self.assertEqual(dct['content'], 'find me some good coffee shops')
        self.assertEqual(dct['id'], message.id)
        self.assertEqual(dct['recipient'], 'Denmark')
        self.assertEqual(dct['sender_realm_str'], 'zulip')
        self.assertEqual(dct['sender_email'], user.email)
        self.assertEqual(dct['sender_full_name'], 'King Hamlet')
        self.assertEqual(dct['sender_id'], user.id)
        self.assertEqual(dct['sender_short_name'], 'hamlet')
        self.assertEqual(dct['sending_client'], 'test suite')
        self.assertEqual(dct[DB_TOPIC_NAME], 'Copenhagen')
        self.assertEqual(dct['type'], 'stream')

class CheckMessageTest(ZulipTestCase):
    def test_basic_check_message_call(self) -> None:
        sender = self.example_user('othello')
        client = make_client(name="test suite")
        stream_name = 'España y Francia'
        self.make_stream(stream_name)
        topic_name = 'issue'
        message_content = 'whatever'
        addressee = Addressee.for_stream_name(stream_name, topic_name)
        ret = check_message(sender, client, addressee, message_content)
        self.assertEqual(ret['message'].sender.id, sender.id)

    def test_bot_pm_feature(self) -> None:
        """We send a PM to a bot's owner if their bot sends a message to
        an unsubscribed stream"""
        parent = self.example_user('othello')
        bot = do_create_user(
            email='othello-bot@zulip.com',
            password='',
            realm=parent.realm,
            full_name='',
            short_name='',
            bot_type=UserProfile.DEFAULT_BOT,
            bot_owner=parent,
        )
        bot.last_reminder = None

        sender = bot
        client = make_client(name="test suite")
        stream_name = 'Россия'
        topic_name = 'issue'
        addressee = Addressee.for_stream_name(stream_name, topic_name)
        message_content = 'whatever'
        old_count = message_stream_count(parent)

        # Try sending to stream that doesn't exist sends a reminder to
        # the sender
        with self.assertRaises(JsonableError):
            check_message(sender, client, addressee, message_content)

        new_count = message_stream_count(parent)
        self.assertEqual(new_count, old_count + 1)
        self.assertIn("that stream does not exist.", most_recent_message(parent).content)

        # Try sending to stream that exists with no subscribers soon
        # after; due to rate-limiting, this should send nothing.
        self.make_stream(stream_name)
        ret = check_message(sender, client, addressee, message_content)
        new_count = message_stream_count(parent)
        self.assertEqual(new_count, old_count + 1)

        # Try sending to stream that exists with no subscribers longer
        # after; this should send an error to the bot owner that the
        # stream doesn't exist
        assert(sender.last_reminder is not None)
        sender.last_reminder = sender.last_reminder - datetime.timedelta(hours=1)
        sender.save(update_fields=["last_reminder"])
        ret = check_message(sender, client, addressee, message_content)

        new_count = message_stream_count(parent)
        self.assertEqual(new_count, old_count + 2)
        self.assertEqual(ret['message'].sender.email, 'othello-bot@zulip.com')
        self.assertIn("does not have any subscribers", most_recent_message(parent).content)

    def test_bot_pm_error_handling(self) -> None:
        # This just test some defensive code.
        cordelia = self.example_user('cordelia')
        test_bot = self.create_test_bot(
            short_name='test',
            user_profile=cordelia,
        )
        content = 'whatever'
        good_realm = test_bot.realm
        wrong_realm = get_realm("zephyr")
        wrong_sender = cordelia

        send_rate_limited_pm_notification_to_bot_owner(test_bot, wrong_realm, content)
        self.assertEqual(test_bot.last_reminder, None)

        send_rate_limited_pm_notification_to_bot_owner(wrong_sender, good_realm, content)
        self.assertEqual(test_bot.last_reminder, None)

        test_bot.realm.deactivated = True
        send_rate_limited_pm_notification_to_bot_owner(test_bot, good_realm, content)
        self.assertEqual(test_bot.last_reminder, None)

class MessageVisibilityTest(ZulipTestCase):
    def test_update_first_visible_message_id(self) -> None:
        Message.objects.all().delete()
        message_ids = [self.send_stream_message(self.example_user("othello"), "Scotland") for i in range(15)]

        # If message_visibility_limit is None update_first_visible_message_id
        # should set first_visible_message_id to 0
        realm = get_realm("zulip")
        realm.message_visibility_limit = None
        # Setting to a random value other than 0 as the default value of
        # first_visible_message_id is 0
        realm.first_visible_message_id = 5
        realm.save()
        update_first_visible_message_id(realm)
        self.assertEqual(get_first_visible_message_id(realm), 0)

        realm.message_visibility_limit = 10
        realm.save()
        expected_message_id = message_ids[5]
        update_first_visible_message_id(realm)
        self.assertEqual(get_first_visible_message_id(realm), expected_message_id)

        # If the message_visibility_limit is greater than number of messages
        # get_first_visible_message_id should return 0
        realm.message_visibility_limit = 50
        realm.save()
        update_first_visible_message_id(realm)
        self.assertEqual(get_first_visible_message_id(realm), 0)

    def test_maybe_update_first_visible_message_id(self) -> None:
        realm = get_realm("zulip")
        lookback_hours = 30

        realm.message_visibility_limit = None
        realm.save()

        end_time = timezone_now() - datetime.timedelta(hours=lookback_hours - 5)
        stat = COUNT_STATS['messages_sent:is_bot:hour']

        RealmCount.objects.create(realm=realm, property=stat.property,
                                  end_time=end_time, value=5)
        with mock.patch("zerver.lib.message.update_first_visible_message_id") as m:
            maybe_update_first_visible_message_id(realm, lookback_hours)
        m.assert_not_called()

        realm.message_visibility_limit = 10
        realm.save()
        RealmCount.objects.all().delete()
        with mock.patch("zerver.lib.message.update_first_visible_message_id") as m:
            maybe_update_first_visible_message_id(realm, lookback_hours)
        m.assert_not_called()

        RealmCount.objects.create(realm=realm, property=stat.property,
                                  end_time=end_time, value=5)
        with mock.patch("zerver.lib.message.update_first_visible_message_id") as m:
            maybe_update_first_visible_message_id(realm, lookback_hours)
        m.assert_called_once_with(realm)

class TestBulkGetHuddleUserIds(ZulipTestCase):
    def test_bulk_get_huddle_user_ids(self) -> None:
        hamlet = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')
        othello = self.example_user('othello')
        iago = self.example_user('iago')
        message_ids = [
            self.send_huddle_message(hamlet, [cordelia, othello], 'test'),
            self.send_huddle_message(cordelia, [hamlet, othello, iago], 'test'),
        ]

        messages = Message.objects.filter(id__in=message_ids).order_by("id")
        first_huddle_recipient = messages[0].recipient
        first_huddle_user_ids = list(get_huddle_user_ids(first_huddle_recipient))
        second_huddle_recipient = messages[1].recipient
        second_huddle_user_ids = list(get_huddle_user_ids(second_huddle_recipient))

        huddle_user_ids = bulk_get_huddle_user_ids([first_huddle_recipient, second_huddle_recipient])
        self.assertEqual(huddle_user_ids[first_huddle_recipient.id], first_huddle_user_ids)
        self.assertEqual(huddle_user_ids[second_huddle_recipient.id], second_huddle_user_ids)

    def test_bulk_get_huddle_user_ids_empty_list(self) -> None:
        self.assertEqual(bulk_get_huddle_user_ids([]), {})

class NoRecipientIDsTest(ZulipTestCase):
    def test_no_recipient_ids(self) -> None:
        user_profile = self.example_user('cordelia')

        Subscription.objects.filter(user_profile=user_profile, recipient__type=Recipient.STREAM).delete()
        subs = gather_subscriptions_helper(user_profile)

        # Checks that gather_subscriptions_helper will not return anything
        # since there will not be any recipients, without crashing.
        #
        # This covers a rare corner case.
        self.assertEqual(len(subs[0]), 0)
