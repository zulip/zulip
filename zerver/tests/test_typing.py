# -*- coding: utf-8 -*-

import ujson
from typing import Any, Mapping, List

from django.core.exceptions import ValidationError

from zerver.lib.actions import recipient_for_user_ids
from zerver.lib.test_helpers import tornado_redirected_to_list
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.models import get_display_recipient

class TypingNotificationOperatorTest(ZulipTestCase):
    def test_missing_parameter(self) -> None:
        """
        Sending typing notification without op parameter fails
        """
        sender = self.example_email("hamlet")
        recipient = self.example_email("othello")
        result = self.api_post(sender, '/api/v1/typing', {'to': recipient})
        self.assert_json_error(result, 'Missing \'op\' argument')

    def test_invalid_parameter(self) -> None:
        """
        Sending typing notification with invalid value for op parameter fails
        """
        sender = self.example_email("hamlet")
        recipient = self.example_email("othello")
        result = self.api_post(sender, '/api/v1/typing', {'to': recipient, 'op': 'foo'})
        self.assert_json_error(result, 'Invalid \'op\' value (should be start or stop)')

class TypingNotificationRecipientsTest(ZulipTestCase):
    def test_missing_recipient(self) -> None:
        """
        Sending typing notification without recipient fails
        """
        sender = self.example_email("hamlet")
        result = self.api_post(sender, '/api/v1/typing', {'op': 'start'})
        self.assert_json_error(result, 'Missing parameter: \'to\' (recipient)')

    def test_invalid_recipient(self) -> None:
        """
        Sending typing notification to invalid recipient fails
        """
        sender = self.example_email("hamlet")
        invalid = 'invalid email'
        result = self.api_post(sender, '/api/v1/typing', {'op': 'start', 'to': invalid})
        self.assert_json_error(result, 'Invalid email \'' + invalid + '\'')

    def test_single_recipient(self) -> None:
        """
        Sending typing notification to a single recipient is successful
        """
        sender = self.example_user('hamlet')
        recipient = self.example_user('othello')
        expected_recipients = set([sender, recipient])
        expected_recipient_emails = set([user.email for user in expected_recipients])
        expected_recipient_ids = set([user.id for user in expected_recipients])

        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.api_post(sender.email, '/api/v1/typing', {'to': recipient.email,
                                                                    'op': 'start'})
        self.assert_json_success(result)
        self.assertEqual(len(events), 1)

        event = events[0]['event']
        event_recipient_emails = set(user['email'] for user in event['recipients'])
        event_user_ids = set(events[0]['users'])
        event_recipient_user_ids = set(user['user_id'] for user in event['recipients'])

        self.assertEqual(expected_recipient_ids, event_recipient_user_ids)
        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event['sender']['email'], sender.email)
        self.assertEqual(event_recipient_emails, expected_recipient_emails)
        self.assertEqual(event['type'], 'typing')
        self.assertEqual(event['op'], 'start')

    def test_single_recipient_by_user_id(self) -> None:
        """
        Sending typing notification to a single recipient (using user IDs)
        is successful
        """
        sender = self.example_user('hamlet')
        recipient_user = self.example_user('othello')
        expected_recipients = set([sender, recipient_user])
        expected_recipient_emails = set([user.email for user in expected_recipients])
        expected_recipient_ids = set([user.id for user in expected_recipients])

        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.api_post(
                sender.email,
                '/api/v1/typing',
                {
                    'to': ujson.dumps([recipient_user.id]),
                    'op': 'start'
                }
            )

        self.assert_json_success(result)
        self.assertEqual(len(events), 1)

        event = events[0]['event']
        event_recipient_emails = set(user['email'] for user in event['recipients'])
        event_user_ids = set(events[0]['users'])
        event_recipient_user_ids = set(user['user_id'] for user in event['recipients'])

        self.assertEqual(expected_recipient_ids, event_recipient_user_ids)
        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event['sender']['email'], sender.email)
        self.assertEqual(event_recipient_emails, expected_recipient_emails)
        self.assertEqual(event['type'], 'typing')
        self.assertEqual(event['op'], 'start')

    def test_multiple_recipients(self) -> None:
        """
        Sending typing notification to a single recipient is successful
        """
        sender = self.example_user('hamlet')
        recipient = [self.example_user('othello'), self.example_user('cordelia')]
        expected_recipients = set(recipient) | set([sender])
        expected_recipient_emails = set([user.email for user in expected_recipients])
        expected_recipient_ids = set([user.id for user in expected_recipients])
        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.api_post(sender.email, '/api/v1/typing',
                                   {'to': ujson.dumps([user.email for user in recipient]),
                                    'op': 'start'})
        self.assert_json_success(result)
        self.assertEqual(len(events), 1)

        event = events[0]['event']
        event_recipient_emails = set(user['email'] for user in event['recipients'])
        event_user_ids = set(events[0]['users'])
        event_recipient_user_ids = set(user['user_id'] for user in event['recipients'])

        self.assertEqual(expected_recipient_ids, event_recipient_user_ids)
        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event['sender']['email'], sender.email)
        self.assertEqual(event_recipient_emails, expected_recipient_emails)
        self.assertEqual(event['type'], 'typing')
        self.assertEqual(event['op'], 'start')

    def test_multiple_recipients_by_user_ids(self) -> None:
        """
        Sending typing notification to multiple recipients (using user IDs)
        is successful
        """
        sender = self.example_user('hamlet')
        recipient_users = [self.example_user('othello'), self.example_user('cordelia')]
        expected_recipients = set(recipient_users) | set([sender])
        expected_recipient_emails = set([user.email for user in expected_recipients])
        expected_recipient_ids = set([user.id for user in expected_recipients])
        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.api_post(sender.email, '/api/v1/typing',
                                   {'to': ujson.dumps([user.id for user in recipient_users]),
                                    'op': 'start'})
        self.assert_json_success(result)
        self.assertEqual(len(events), 1)

        event = events[0]['event']
        event_recipient_emails = set(user['email'] for user in event['recipients'])
        event_user_ids = set(events[0]['users'])
        event_recipient_user_ids = set(user['user_id'] for user in event['recipients'])

        self.assertEqual(expected_recipient_ids, event_recipient_user_ids)
        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event['sender']['email'], sender.email)
        self.assertEqual(event_recipient_emails, expected_recipient_emails)
        self.assertEqual(event['type'], 'typing')
        self.assertEqual(event['op'], 'start')

class TypingStartedNotificationTest(ZulipTestCase):
    def test_send_notification_to_self_event(self) -> None:
        """
        Sending typing notification to yourself
        is successful.
        """
        user = self.example_user('hamlet')
        email = user.email
        expected_recipient_emails = set([email])
        expected_recipient_ids = set([user.id])
        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.api_post(email, '/api/v1/typing', {'to': email,
                                                             'op': 'start'})
        self.assert_json_success(result)
        self.assertEqual(len(events), 1)

        event = events[0]['event']
        event_recipient_emails = set(user['email'] for user in event['recipients'])
        event_user_ids = set(events[0]['users'])
        event_recipient_user_ids = set(user['user_id'] for user in event['recipients'])

        self.assertEqual(expected_recipient_ids, event_recipient_user_ids)
        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event_recipient_emails, expected_recipient_emails)
        self.assertEqual(event['sender']['email'], email)
        self.assertEqual(event['type'], 'typing')
        self.assertEqual(event['op'], 'start')

    def test_send_notification_to_self_by_user_id_event(self) -> None:
        """
        Sending typing notification to yourself (using user IDs)
        is successful.
        """
        user = self.example_user('hamlet')
        email = user.email
        expected_recipient_emails = set([email])
        expected_recipient_ids = set([user.id])
        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.api_post(
                email,
                '/api/v1/typing',
                {
                    'to': ujson.dumps([user.id]),
                    'op': 'start'
                }
            )
        self.assert_json_success(result)
        self.assertEqual(len(events), 1)

        event = events[0]['event']
        event_recipient_emails = set(user['email'] for user in event['recipients'])
        event_user_ids = set(events[0]['users'])
        event_recipient_user_ids = set(user['user_id'] for user in event['recipients'])

        self.assertEqual(expected_recipient_ids, event_recipient_user_ids)
        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event_recipient_emails, expected_recipient_emails)
        self.assertEqual(event['sender']['email'], email)
        self.assertEqual(event['type'], 'typing')
        self.assertEqual(event['op'], 'start')

    def test_send_notification_to_another_user_event(self) -> None:
        """
        Sending typing notification to another user
        is successful.
        """
        sender = self.example_user('hamlet')
        recipient = self.example_user('othello')
        expected_recipients = set([sender, recipient])
        expected_recipient_emails = set([user.email for user in expected_recipients])
        expected_recipient_ids = set([user.id for user in expected_recipients])

        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.api_post(sender.email, '/api/v1/typing', {'to': recipient.email,
                                                                    'op': 'start'})
        self.assert_json_success(result)
        self.assertEqual(len(events), 1)

        event = events[0]['event']
        event_recipient_emails = set(user['email'] for user in event['recipients'])
        event_user_ids = set(events[0]['users'])
        event_recipient_user_ids = set(user['user_id'] for user in event['recipients'])

        self.assertEqual(expected_recipient_ids, event_recipient_user_ids)
        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event_recipient_emails, expected_recipient_emails)
        self.assertEqual(event['sender']['email'], sender.email)
        self.assertEqual(event['type'], 'typing')
        self.assertEqual(event['op'], 'start')

class StoppedTypingNotificationTest(ZulipTestCase):
    def test_send_notification_to_self_event(self) -> None:
        """
        Sending stopped typing notification to yourself
        is successful.
        """
        user = self.example_user('hamlet')
        email = user.email
        expected_recipient_emails = set([email])
        expected_recipient_ids = set([user.id])

        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.api_post(email, '/api/v1/typing', {'to': email,
                                                             'op': 'stop'})
        self.assert_json_success(result)
        self.assertEqual(len(events), 1)

        event = events[0]['event']
        event_recipient_emails = set(user['email'] for user in event['recipients'])
        event_user_ids = set(events[0]['users'])
        event_recipient_user_ids = set(user['user_id'] for user in event['recipients'])

        self.assertEqual(expected_recipient_ids, event_recipient_user_ids)
        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event_recipient_emails, expected_recipient_emails)
        self.assertEqual(event['sender']['email'], email)
        self.assertEqual(event['type'], 'typing')
        self.assertEqual(event['op'], 'stop')

    def test_send_notification_to_another_user_event(self) -> None:
        """
        Sending stopped typing notification to another user
        is successful.
        """
        sender = self.example_user('hamlet')
        recipient = self.example_user('othello')
        expected_recipients = set([sender, recipient])
        expected_recipient_emails = set([user.email for user in expected_recipients])
        expected_recipient_ids = set([user.id for user in expected_recipients])

        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.api_post(sender.email, '/api/v1/typing', {'to': recipient.email,
                                                                    'op': 'stop'})
        self.assert_json_success(result)
        self.assertEqual(len(events), 1)

        event = events[0]['event']
        event_recipient_emails = set(user['email'] for user in event['recipients'])
        event_user_ids = set(events[0]['users'])
        event_recipient_user_ids = set(user['user_id'] for user in event['recipients'])

        self.assertEqual(expected_recipient_ids, event_recipient_user_ids)
        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event_recipient_emails, expected_recipient_emails)
        self.assertEqual(event['sender']['email'], sender.email)
        self.assertEqual(event['type'], 'typing')
        self.assertEqual(event['op'], 'stop')

class TypingValidationHelpersTest(ZulipTestCase):
    def test_recipient_for_user_ids(self) -> None:
        hamlet = self.example_user('hamlet')
        othello = self.example_user('othello')
        cross_realm_bot = self.example_user('welcome_bot')
        sender = self.example_user('iago')
        recipient_user_ids = [hamlet.id, othello.id, cross_realm_bot.id]

        result = recipient_for_user_ids(recipient_user_ids, sender)
        recipient = get_display_recipient(result)
        recipient_ids = [recipient[0]['id'], recipient[1]['id'],  # type: ignore
                         recipient[2]['id'], recipient[3]['id']]  # type: ignore

        expected_recipient_ids = [hamlet.id, othello.id,
                                  sender.id, cross_realm_bot.id]
        self.assertEqual(set(recipient_ids), set(expected_recipient_ids))

    def test_recipient_for_user_ids_non_existent_id(self) -> None:
        sender = self.example_user('iago')
        recipient_user_ids = [999]

        with self.assertRaisesRegex(ValidationError, 'Invalid user ID '):
            recipient_for_user_ids(recipient_user_ids, sender)
