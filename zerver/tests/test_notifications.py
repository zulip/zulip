
import os
import random
import re
import ujson

from django.conf import settings
from django.core import mail
from django.http import HttpResponse
from django.test import override_settings
from email.utils import formataddr
from mock import patch, MagicMock
from typing import Any, Dict, List, Text, Optional

from zerver.lib.notifications import fix_emojis, \
    handle_missedmessage_emails, relative_to_full_url
from zerver.lib.actions import do_update_message, \
    do_change_notification_settings
from zerver.lib.message import access_message
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.send_email import FromAddress
from zerver.models import (
    get_realm,
    get_stream,
    Recipient,
    UserMessage,
    UserProfile,
)
from zerver.lib.test_helpers import get_test_image_file

class TestMissedMessages(ZulipTestCase):
    def normalize_string(self, s: Text) -> Text:
        s = s.strip()
        return re.sub(r'\s+', ' ', s)

    def _get_tokens(self) -> List[str]:
        return [str(random.getrandbits(32)) for _ in range(30)]

    def _test_cases(self, tokens: List[str], msg_id: int, body: str, subject: str,
                    send_as_user: bool, verify_html_body: bool=False,
                    show_message_content: bool=True,
                    verify_body_does_not_include: Optional[List[str]]=None) -> None:
        othello = self.example_user('othello')
        hamlet = self.example_user('hamlet')
        handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id}])
        if settings.EMAIL_GATEWAY_PATTERN != "":
            reply_to_addresses = [settings.EMAIL_GATEWAY_PATTERN % (u'mm' + t) for t in tokens]
            reply_to_emails = [formataddr(("Zulip", address)) for address in reply_to_addresses]
        else:
            reply_to_emails = ["noreply@testserver"]
        msg = mail.outbox[0]
        from_email = formataddr(("Zulip missed messages", FromAddress.NOREPLY))
        self.assertEqual(len(mail.outbox), 1)
        if send_as_user:
            from_email = '"%s" <%s>' % (othello.full_name, othello.email)
        self.assertEqual(msg.from_email, from_email)
        self.assertEqual(msg.subject, subject)
        self.assertEqual(len(msg.reply_to), 1)
        self.assertIn(msg.reply_to[0], reply_to_emails)
        if verify_html_body:
            self.assertIn(body, self.normalize_string(msg.alternatives[0][0]))
        else:
            self.assertIn(body, self.normalize_string(msg.body))
        if verify_body_does_not_include is not None:
            for text in verify_body_does_not_include:
                self.assertNotIn(text, self.normalize_string(msg.body))

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _realm_name_in_missed_message_email_subject(self,
                                                    realm_name_in_notifications: bool,
                                                    mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_personal_message(
            self.example_email('othello'),
            self.example_email('hamlet'),
            'Extremely personal message!',
        )
        body = 'You and Othello, the Moor of Venice Extremely personal message!'
        subject = 'Othello, the Moor of Venice sent you a message'

        if realm_name_in_notifications:
            subject = 'Othello, the Moor of Venice sent you a message in Zulip Dev'
        self._test_cases(tokens, msg_id, body, subject, False)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_missed_stream_messages_mention(self, send_as_user: bool,
                                                         mock_random_token: MagicMock,
                                                         show_message_content: bool=True) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        for i in range(0, 11):
            self.send_stream_message(self.example_email('othello'), "Denmark", content=str(i))
        self.send_stream_message(
            self.example_email('othello'), "Denmark",
            '11', topic_name='test2')
        msg_id = self.send_stream_message(
            self.example_email('othello'), "denmark",
            '@**King Hamlet**')

        if show_message_content:
            body = 'Denmark > test Othello, the Moor of Venice 1 2 3 4 5 6 7 8 9 10 @**King Hamlet**'
            subject = 'Othello, the Moor of Venice mentioned you'
            verify_body_does_not_include = []  # type: List[str]
        else:
            # Test in case if message content in missed email message are disabled.
            body = 'While you were away you received 1 new message in which you were mentioned!'
            subject = 'New missed message'
            verify_body_does_not_include = ['Denmark > test', 'Othello, the Moor of Venice',
                                            '1 2 3 4 5 6 7 8 9 10 @**King Hamlet**', 'private', 'group',
                                            'Or just reply to this email.']
        self._test_cases(tokens, msg_id, body, subject, send_as_user,
                         show_message_content=show_message_content,
                         verify_body_does_not_include=verify_body_does_not_include)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_missed_stream_messages_mention_two_senders(
            self, send_as_user: bool, mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        for i in range(0, 3):
            self.send_stream_message(self.example_email('cordelia'), "Denmark", str(i))
        msg_id = self.send_stream_message(
            self.example_email('othello'), "Denmark",
            '@**King Hamlet**')
        body = 'Denmark > test Cordelia Lear 0 1 2 Othello, the Moor of Venice @**King Hamlet**'
        subject = 'Othello, the Moor of Venice mentioned you'
        self._test_cases(tokens, msg_id, body, subject, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_personal_missed_stream_messages(self, send_as_user: bool,
                                                          mock_random_token: MagicMock,
                                                          show_message_content: bool=True) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_personal_message(
            self.example_email('othello'),
            self.example_email('hamlet'),
            'Extremely personal message!',
        )

        if show_message_content:
            body = 'You and Othello, the Moor of Venice Extremely personal message!'
            subject = 'Othello, the Moor of Venice sent you a message'
            verify_body_does_not_include = []  # type: List[str]
        else:
            body = 'While you were away you received 1 new private message!'
            subject = 'New missed message'
            verify_body_does_not_include = ['Othello, the Moor of Venice', 'Extremely personal message!',
                                            'mentioned', 'group', 'Or just reply to this email.']
        self._test_cases(tokens, msg_id, body, subject, send_as_user,
                         show_message_content=show_message_content,
                         verify_body_does_not_include=verify_body_does_not_include)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _reply_to_email_in_personal_missed_stream_messages(self, send_as_user: bool,
                                                           mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_personal_message(
            self.example_email('othello'),
            self.example_email('hamlet'),
            'Extremely personal message!',
        )
        body = 'Or just reply to this email.'
        subject = 'Othello, the Moor of Venice sent you a message'
        self._test_cases(tokens, msg_id, body, subject, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _reply_warning_in_personal_missed_stream_messages(self, send_as_user: bool,
                                                          mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_personal_message(
            self.example_email('othello'),
            self.example_email('hamlet'),
            'Extremely personal message!',
        )
        body = 'Please do not reply to this automated message.'
        subject = 'Othello, the Moor of Venice sent you a message'
        self._test_cases(tokens, msg_id, body, subject, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_huddle_missed_stream_messages_two_others(self, send_as_user: bool,
                                                                   mock_random_token: MagicMock,
                                                                   show_message_content: bool=True) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_huddle_message(
            self.example_email('othello'),
            [
                self.example_email('hamlet'),
                self.example_email('iago'),
            ],
            'Group personal message!',
        )

        if show_message_content:
            body = ('You and Iago, Othello, the Moor of Venice Othello,'
                    ' the Moor of Venice Group personal message')
            subject = 'Group PMs with Iago and Othello, the Moor of Venice'
            verify_body_does_not_include = []  # type: List[str]
        else:
            body = 'While you were away you received 1 new group private message!'
            subject = 'New missed message'
            verify_body_does_not_include = ['Iago', 'Othello, the Moor of Venice Othello, the Moor of Venice',
                                            'Group personal message!', 'mentioned',
                                            'Or just reply to this email.']
        self._test_cases(tokens, msg_id, body, subject, send_as_user,
                         show_message_content=show_message_content,
                         verify_body_does_not_include=verify_body_does_not_include)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_huddle_missed_stream_messages_three_others(self, send_as_user: bool,
                                                                     mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_huddle_message(
            self.example_email('othello'),
            [
                self.example_email('hamlet'),
                self.example_email('iago'),
                self.example_email('cordelia'),
            ],
            'Group personal message!',
        )

        body = ('You and Cordelia Lear, Iago, Othello, the Moor of Venice Othello,'
                ' the Moor of Venice Group personal message')
        subject = 'Group PMs with Cordelia Lear, Iago, and Othello, the Moor of Venice'
        self._test_cases(tokens, msg_id, body, subject, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_huddle_missed_stream_messages_many_others(self, send_as_user: bool,
                                                                    mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_huddle_message(self.example_email('othello'),
                                          [self.example_email('hamlet'),
                                           self.example_email('iago'),
                                           self.example_email('cordelia'),
                                           self.example_email('prospero')],
                                          'Group personal message!')

        body = ('You and Cordelia Lear, Iago, Othello, the Moor of Venice, Prospero from The Tempest'
                ' Othello, the Moor of Venice Group personal message')
        subject = 'Group PMs with Cordelia Lear, Iago, and 2 others'
        self._test_cases(tokens, msg_id, body, subject, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _deleted_message_in_missed_stream_messages(self, send_as_user: bool,
                                                   mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_stream_message(
            self.example_email('othello'), "denmark",
            '@**King Hamlet** to be deleted')

        hamlet = self.example_user('hamlet')
        email = self.example_email('othello')
        self.login(email)
        result = self.client_patch('/json/messages/' + str(msg_id),
                                   {'message_id': msg_id, 'content': ' '})
        self.assert_json_success(result)
        handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id}])
        self.assertEqual(len(mail.outbox), 0)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _deleted_message_in_personal_missed_stream_messages(self, send_as_user: bool,
                                                            mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_personal_message(self.example_email('othello'),
                                            self.example_email('hamlet'),
                                            'Extremely personal message! to be deleted!')

        hamlet = self.example_user('hamlet')
        email = self.example_email('othello')
        self.login(email)
        result = self.client_patch('/json/messages/' + str(msg_id),
                                   {'message_id': msg_id, 'content': ' '})
        self.assert_json_success(result)
        handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id}])
        self.assertEqual(len(mail.outbox), 0)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _deleted_message_in_huddle_missed_stream_messages(self, send_as_user: bool,
                                                          mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_huddle_message(
            self.example_email('othello'),
            [
                self.example_email('hamlet'),
                self.example_email('iago'),
            ],
            'Group personal message!',
        )

        hamlet = self.example_user('hamlet')
        iago = self.example_user('iago')
        email = self.example_email('othello')
        self.login(email)
        result = self.client_patch('/json/messages/' + str(msg_id),
                                   {'message_id': msg_id, 'content': ' '})
        self.assert_json_success(result)
        handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id}])
        self.assertEqual(len(mail.outbox), 0)
        handle_missedmessage_emails(iago.id, [{'message_id': msg_id}])
        self.assertEqual(len(mail.outbox), 0)

    def test_realm_name_in_notifications(self) -> None:
        # Test with realm_name_in_notifications for hamlet disabled.
        self._realm_name_in_missed_message_email_subject(False)

        # Enable realm_name_in_notifications for hamlet and test again.
        hamlet = self.example_user('hamlet')
        hamlet.realm_name_in_notifications = True
        hamlet.save(update_fields=['realm_name_in_notifications'])

        # Empty the test outbox
        mail.outbox = []
        self._realm_name_in_missed_message_email_subject(True)

    def test_message_content_disabled_in_missed_message_notifications(self) -> None:
        # Test when user disabled message content in email notifications.
        do_change_notification_settings(self.example_user("hamlet"),
                                        "message_content_in_email_notifications", False)
        self._extra_context_in_missed_stream_messages_mention(False, show_message_content=False)
        mail.outbox = []
        self._extra_context_in_personal_missed_stream_messages(False, show_message_content=False)
        mail.outbox = []
        self._extra_context_in_huddle_missed_stream_messages_two_others(False, show_message_content=False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_missed_stream_messages_as_user(self) -> None:
        self._extra_context_in_missed_stream_messages_mention(True)

    def test_extra_context_in_missed_stream_messages(self) -> None:
        self._extra_context_in_missed_stream_messages_mention(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_missed_stream_messages_as_user_two_senders(self) -> None:
        self._extra_context_in_missed_stream_messages_mention_two_senders(True)

    def test_extra_context_in_missed_stream_messages_two_senders(self) -> None:
        self._extra_context_in_missed_stream_messages_mention_two_senders(False)

    def test_reply_to_email_in_personal_missed_stream_messages(self) -> None:
        self._reply_to_email_in_personal_missed_stream_messages(False)

    @override_settings(EMAIL_GATEWAY_PATTERN="")
    def test_reply_warning_in_personal_missed_stream_messages(self) -> None:
        self._reply_warning_in_personal_missed_stream_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_personal_missed_stream_messages_as_user(self) -> None:
        self._extra_context_in_personal_missed_stream_messages(True)

    def test_extra_context_in_personal_missed_stream_messages(self) -> None:
        self._extra_context_in_personal_missed_stream_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_huddle_missed_stream_messages_two_others_as_user(self) -> None:
        self._extra_context_in_huddle_missed_stream_messages_two_others(True)

    def test_extra_context_in_huddle_missed_stream_messages_two_others(self) -> None:
        self._extra_context_in_huddle_missed_stream_messages_two_others(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_huddle_missed_stream_messages_three_others_as_user(self) -> None:
        self._extra_context_in_huddle_missed_stream_messages_three_others(True)

    def test_extra_context_in_huddle_missed_stream_messages_three_others(self) -> None:
        self._extra_context_in_huddle_missed_stream_messages_three_others(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_huddle_missed_stream_messages_many_others_as_user(self) -> None:
        self._extra_context_in_huddle_missed_stream_messages_many_others(True)

    def test_extra_context_in_huddle_missed_stream_messages_many_others(self) -> None:
        self._extra_context_in_huddle_missed_stream_messages_many_others(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_deleted_message_in_missed_stream_messages_as_user(self) -> None:
        self._deleted_message_in_missed_stream_messages(True)

    def test_deleted_message_in_missed_stream_messages(self) -> None:
        self._deleted_message_in_missed_stream_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_deleted_message_in_personal_missed_stream_messages_as_user(self) -> None:
        self._deleted_message_in_personal_missed_stream_messages(True)

    def test_deleted_message_in_personal_missed_stream_messages(self) -> None:
        self._deleted_message_in_personal_missed_stream_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_deleted_message_in_huddle_missed_stream_messages_as_user(self) -> None:
        self._deleted_message_in_huddle_missed_stream_messages(True)

    def test_deleted_message_in_huddle_missed_stream_messages(self) -> None:
        self._deleted_message_in_huddle_missed_stream_messages(False)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def test_realm_emoji_in_missed_message(self, mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_personal_message(
            self.example_email('othello'), self.example_email('hamlet'),
            'Extremely personal message with a realm emoji :green_tick:!')
        realm_emoji_id = get_realm('zulip').get_active_emoji()['green_tick']['id']
        realm_emoji_url = "http://zulip.testserver/user_avatars/1/emoji/images/%s.png" % (realm_emoji_id,)
        body = '<img alt=":green_tick:" src="%s" title="green tick" style="height: 20px;">' % (realm_emoji_url,)
        subject = 'Othello, the Moor of Venice sent you a message'
        self._test_cases(tokens, msg_id, body, subject, send_as_user=False, verify_html_body=True)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def test_emojiset_in_missed_message(self, mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        hamlet = self.example_user('hamlet')
        hamlet.emojiset = 'apple'
        hamlet.save(update_fields=['emojiset'])
        msg_id = self.send_personal_message(
            self.example_email('othello'), self.example_email('hamlet'),
            'Extremely personal message with a hamburger :hamburger:!')
        body = '<img alt=":hamburger:" src="http://zulip.testserver/static/generated/emoji/images-apple-64/1f354.png" title="hamburger" style="height: 20px;">'
        subject = 'Othello, the Moor of Venice sent you a message'
        self._test_cases(tokens, msg_id, body, subject, send_as_user=False, verify_html_body=True)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def test_stream_link_in_missed_message(self, mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_personal_message(
            self.example_email('othello'), self.example_email('hamlet'),
            'Come and join us in #**Verona**.')
        stream_id = get_stream('Verona', get_realm('zulip')).id
        href = "http://zulip.testserver/#narrow/stream/{stream_id}-Verona".format(stream_id=stream_id)
        body = '<a class="stream" data-stream-id="5" href="{href}">#Verona</a'.format(href=href)
        subject = 'Othello, the Moor of Venice sent you a message'
        self._test_cases(tokens, msg_id, body, subject, send_as_user=False, verify_html_body=True)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def test_multiple_missed_personal_messages(self, mock_random_token: MagicMock) -> None:
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        hamlet = self.example_user('hamlet')
        msg_id_1 = self.send_personal_message(self.example_email('othello'),
                                              hamlet.email,
                                              'Personal Message 1')
        msg_id_2 = self.send_personal_message(self.example_email('iago'),
                                              hamlet.email,
                                              'Personal Message 2')

        handle_missedmessage_emails(hamlet.id, [
            {'message_id': msg_id_1},
            {'message_id': msg_id_2},
        ])
        self.assertEqual(len(mail.outbox), 2)
        subject = 'Iago sent you a message'
        self.assertEqual(mail.outbox[0].subject, subject)
        subject = 'Othello, the Moor of Venice sent you a message'
        self.assertEqual(mail.outbox[1].subject, subject)

    def test_relative_to_full_url(self) -> None:
        # Run `relative_to_full_url()` function over test fixtures present in
        # 'markdown_test_cases.json' and check that it converts all the relative
        # URLs to absolute URLs.
        fixtures_file = os.path.join(settings.DEPLOY_ROOT, "zerver",
                                     "fixtures", "markdown_test_cases.json")
        fixtures = ujson.load(open(fixtures_file))
        test_fixtures = {}
        for test in fixtures['regular_tests']:
            test_fixtures[test['name']] = test
        for test_name in test_fixtures:
            test_data = test_fixtures[test_name]["expected_output"]
            output_data = relative_to_full_url("http://example.com", test_data)
            if re.search("(?<=\=['\"])/(?=[^<]+>)", output_data) is not None:
                raise AssertionError("Relative URL present in email: " + output_data +
                                     "\nFailed test case's name is: " + test_name +
                                     "\nIt is present in markdown_test_cases.json")

        # Specific test cases.

        # A path similar to our emoji path, but not in a link:
        test_data = "<p>Check out the file at: '/static/generated/emoji/images/emoji/'</p>"
        actual_output = relative_to_full_url("http://example.com", test_data)
        expected_output = "<p>Check out the file at: '/static/generated/emoji/images/emoji/'</p>"
        self.assertEqual(actual_output, expected_output)

        # An uploaded file
        test_data = '<a href="/user_uploads/2/1f/some_random_value">/user_uploads/2/1f/some_random_value</a>'
        actual_output = relative_to_full_url("http://example.com", test_data)
        expected_output = '<a href="http://example.com/user_uploads/2/1f/some_random_value">' + \
            '/user_uploads/2/1f/some_random_value</a>'
        self.assertEqual(actual_output, expected_output)

        # A user avatar like syntax, but not actually in an HTML tag
        test_data = '<p>Set src="/avatar/username@example.com?s=30"</p>'
        actual_output = relative_to_full_url("http://example.com", test_data)
        expected_output = '<p>Set src="/avatar/username@example.com?s=30"</p>'
        self.assertEqual(actual_output, expected_output)

        # A narrow URL which begins with a '#'.
        test_data = '<p><a href="#narrow/stream/test/subject/test.20topic/near/142"' +  \
                    'title="#narrow/stream/test/subject/test.20topic/near/142">Conversation</a></p>'
        actual_output = relative_to_full_url("http://example.com", test_data)
        expected_output = '<p><a href="http://example.com/#narrow/stream/test/subject/test.20topic/near/142" ' + \
                          'title="http://example.com/#narrow/stream/test/subject/test.20topic/near/142">Conversation</a></p>'
        self.assertEqual(actual_output, expected_output)

        # Scrub inline images.
        test_data = '<p>See this <a href="/user_uploads/1/52/fG7GM9e3afz_qsiUcSce2tl_/avatar_103.jpeg" target="_blank" ' +   \
                    'title="avatar_103.jpeg">avatar_103.jpeg</a>.</p>' +    \
                    '<div class="message_inline_image"><a href="/user_uploads/1/52/fG7GM9e3afz_qsiUcSce2tl_/avatar_103.jpeg" ' +    \
                    'target="_blank" title="avatar_103.jpeg"><img src="/user_uploads/1/52/fG7GM9e3afz_qsiUcSce2tl_/avatar_103.jpeg"></a></div>'
        actual_output = relative_to_full_url("http://example.com", test_data)
        expected_output = '<div><p>See this <a href="http://example.com/user_uploads/1/52/fG7GM9e3afz_qsiUcSce2tl_/avatar_103.jpeg" target="_blank" ' +  \
                          'title="avatar_103.jpeg">avatar_103.jpeg</a>.</p></div>'
        self.assertEqual(actual_output, expected_output)

        # A message containing only an inline image URL preview, we do
        # somewhat more extensive surgery.
        test_data = '<div class="message_inline_image"><a href="https://www.google.com/images/srpr/logo4w.png" ' + \
                    'target="_blank" title="https://www.google.com/images/srpr/logo4w.png">' + \
                    '<img data-original="/thumbnail/https%3A//www.google.com/images/srpr/logo4w.png?size=0x0" ' + \
                    'src="/thumbnail/https%3A//www.google.com/images/srpr/logo4w.png?size=0x100"></a></div>'
        actual_output = relative_to_full_url("http://example.com", test_data)
        expected_output = '<p><a href="https://www.google.com/images/srpr/logo4w.png" ' + \
                          'target="_blank" title="https://www.google.com/images/srpr/logo4w.png">' + \
                          'https://www.google.com/images/srpr/logo4w.png</a></p>'
        self.assertEqual(actual_output, expected_output)

    def test_fix_emoji(self) -> None:
        # An emoji.
        test_data = '<p>See <span class="emoji emoji-26c8" title="cloud with lightning and rain">' + \
                    ':cloud_with_lightning_and_rain:</span>.</p>'
        actual_output = fix_emojis(test_data, "http://example.com", "google")
        expected_output = '<p>See <img alt=":cloud_with_lightning_and_rain:" src="http://example.com/static/generated/emoji/images-google-64/26c8.png" ' + \
                          'title="cloud with lightning and rain" style="height: 20px;">.</p>'
        self.assertEqual(actual_output, expected_output)
