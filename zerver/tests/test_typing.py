# -*- coding: utf-8 -*-

import ujson
from typing import Any, Mapping, List

from zerver.lib.test_helpers import tornado_redirected_to_list, get_display_recipient
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.models import get_realm, get_user

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
