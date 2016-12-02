# -*- coding: utf-8 -*-
from __future__ import absolute_import

import ujson
from typing import Any, Dict, List
from six import string_types

from zerver.lib.test_helpers import tornado_redirected_to_list, get_display_recipient
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.models import get_user_profile_by_email

class TypingNotificationOperatorTest(ZulipTestCase):
    def test_missing_parameter(self):
        # type: () -> None
        """
        Sending typing notification without op parameter fails
        """
        sender = 'hamlet@zulip.com'
        recipient = 'othello@zulip.com'
        result = self.client_post('/api/v1/typing', {'to': recipient},
                                  **self.api_auth(sender))
        self.assert_json_error(result, 'Missing \'op\' argument')

    def test_invalid_parameter(self):
        # type: () -> None
        """
        Sending typing notification with invalid value for op parameter fails
        """
        sender = 'hamlet@zulip.com'
        recipient = 'othello@zulip.com'
        result = self.client_post('/api/v1/typing', {'to': recipient, 'op': 'foo'},
                                  **self.api_auth(sender))
        self.assert_json_error(result, 'Invalid \'op\' value (should be start or stop)')

class TypingNotificationRecipientsTest(ZulipTestCase):
    def test_missing_recipient(self):
        # type: () -> None
        """
        Sending typing notification without recipient fails
        """
        sender = 'hamlet@zulip.com'
        result = self.client_post('/api/v1/typing', {'op': 'start'},
                                  **self.api_auth(sender))
        self.assert_json_error(result, 'Missing parameter: \'to\' (recipient)')

    def test_invalid_recipient(self):
        # type: () -> None
        """
        Sending typing notification to invalid recipient fails
        """
        sender = 'hamlet@zulip.com'
        invalid = 'invalid email'
        result = self.client_post('/api/v1/typing', {'op': 'start', 'to': invalid},
                                  **self.api_auth(sender))
        self.assert_json_error(result, 'Invalid email \'' + invalid + '\'')

    def test_single_recipient(self):
        # type: () -> None
        """
        Sending typing notification to a single recipient is successful
        """
        sender = 'hamlet@zulip.com'
        recipient = 'othello@zulip.com'
        expected_recipient_emails = set([sender, recipient])
        expected_recipient_ids = set([get_user_profile_by_email(email).id for email in expected_recipient_emails])

        events = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.client_post('/api/v1/typing', {'to': recipient,
                                                         'op': 'start'},
                                      **self.api_auth(sender))
        self.assert_json_success(result)
        self.assertEqual(len(events), 1)

        event = events[0]['event']
        event_recipient_emails = set(user['email'] for user in event['recipients'])
        event_user_ids = set(events[0]['users'])
        event_recipient_user_ids = set(user['user_id'] for user in event['recipients'])

        self.assertEqual(expected_recipient_ids, event_recipient_user_ids)
        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event['sender']['email'], sender)
        self.assertEqual(event_recipient_emails, expected_recipient_emails)
        self.assertEqual(event['type'], 'typing')
        self.assertEqual(event['op'], 'start')

    def test_multiple_recipients(self):
        # type: () -> None
        """
        Sending typing notification to a single recipient is successful
        """
        sender = 'hamlet@zulip.com'
        recipient = ['othello@zulip.com', 'cordelia@zulip.com']
        expected_recipient_emails = set(recipient) | set([sender])
        expected_recipient_ids = set([get_user_profile_by_email(email).id for email in expected_recipient_emails])
        events = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.client_post('/api/v1/typing', {'to': ujson.dumps(recipient),
                                                         'op': 'start'},
                                      **self.api_auth(sender))
        self.assert_json_success(result)
        self.assertEqual(len(events), 1)

        event = events[0]['event']
        event_recipient_emails = set(user['email'] for user in event['recipients'])
        event_user_ids = set(events[0]['users'])
        event_recipient_user_ids = set(user['user_id'] for user in event['recipients'])

        self.assertEqual(expected_recipient_ids, event_recipient_user_ids)
        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event['sender']['email'], sender)
        self.assertEqual(event_recipient_emails, expected_recipient_emails)
        self.assertEqual(event['type'], 'typing')
        self.assertEqual(event['op'], 'start')

class TypingStartedNotificationTest(ZulipTestCase):
    def test_send_notification_to_self_event(self):
        # type: () -> None
        """
        Sending typing notification to yourself
        is successful.
        """
        email = 'hamlet@zulip.com'
        expected_recipient_emails = set([email])
        expected_recipient_ids = set([get_user_profile_by_email(email).id])
        events = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.client_post('/api/v1/typing', {'to': email,
                                                         'op': 'start'},
                                      **self.api_auth(email))
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

    def test_send_notification_to_another_user_event(self):
        # type: () -> None
        """
        Sending typing notification to another user
        is successful.
        """
        sender = 'hamlet@zulip.com'
        recipient = 'othello@zulip.com'
        expected_recipient_emails = set([sender, recipient])
        expected_recipient_ids = set([get_user_profile_by_email(email).id for email in expected_recipient_emails])

        events = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.client_post('/api/v1/typing', {'to': recipient,
                                                         'op': 'start'},
                                      **self.api_auth(sender))
        self.assert_json_success(result)
        self.assertEqual(len(events), 1)

        event = events[0]['event']
        event_recipient_emails = set(user['email'] for user in event['recipients'])
        event_user_ids = set(events[0]['users'])
        event_recipient_user_ids = set(user['user_id'] for user in event['recipients'])

        self.assertEqual(expected_recipient_ids, event_recipient_user_ids)
        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event_recipient_emails, expected_recipient_emails)
        self.assertEqual(event['sender']['email'], sender)
        self.assertEqual(event['type'], 'typing')
        self.assertEqual(event['op'], 'start')

class StoppedTypingNotificationTest(ZulipTestCase):
    def test_send_notification_to_self_event(self):
        # type: () -> None
        """
        Sending stopped typing notification to yourself
        is successful.
        """
        email = 'hamlet@zulip.com'
        expected_recipient_emails = set([email])
        expected_recipient_ids = set([get_user_profile_by_email(email).id])

        events = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.client_post('/api/v1/typing', {'to': email,
                                                         'op': 'stop'},
                                      **self.api_auth(email))
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

    def test_send_notification_to_another_user_event(self):
        # type: () -> None
        """
        Sending stopped typing notification to another user
        is successful.
        """
        sender = 'hamlet@zulip.com'
        recipient = 'othello@zulip.com'
        expected_recipient_emails = set([sender, recipient])
        expected_recipient_ids = set([get_user_profile_by_email(email).id for email in expected_recipient_emails])

        events = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.client_post('/api/v1/typing', {'to': recipient,
                                                         'op': 'stop'},
                                      **self.api_auth(sender))
        self.assert_json_success(result)
        self.assertEqual(len(events), 1)

        event = events[0]['event']
        event_recipient_emails = set(user['email'] for user in event['recipients'])
        event_user_ids = set(events[0]['users'])
        event_recipient_user_ids = set(user['user_id'] for user in event['recipients'])

        self.assertEqual(expected_recipient_ids, event_recipient_user_ids)
        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event_recipient_emails, expected_recipient_emails)
        self.assertEqual(event['sender']['email'], sender)
        self.assertEqual(event['type'], 'typing')
        self.assertEqual(event['op'], 'stop')
