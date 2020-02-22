# -*- coding: utf-8 -*-

import ujson
from typing import Any, Mapping, List

from django.conf import settings
from django.core.exceptions import ValidationError

from zerver.lib.actions import recipient_for_user_ids
from zerver.lib.test_helpers import (
    tornado_redirected_to_list,
    queries_captured,
)
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.models import (
    Huddle,
    get_display_recipient,
    get_huddle_hash,
    get_system_bot,
)

class TypingValidateOperatorTest(ZulipTestCase):
    def test_missing_parameter(self) -> None:
        """
        Sending typing notification without op parameter fails
        """
        sender = self.example_user("hamlet")
        params = dict(
            to=ujson.dumps([sender.id]),
        )
        result = self.api_post(sender.email, '/api/v1/typing', params)
        self.assert_json_error(result, 'Missing \'op\' argument')

    def test_invalid_parameter(self) -> None:
        """
        Sending typing notification with invalid value for op parameter fails
        """
        sender = self.example_user("hamlet")
        params = dict(
            to=ujson.dumps([sender.id]),
            op='foo'
        )
        result = self.api_post(sender.email, '/api/v1/typing', params)
        self.assert_json_error(result, 'Invalid \'op\' value (should be start or stop)')

class TypingValidateUsersTest(ZulipTestCase):
    def test_empty_array(self) -> None:
        """
        Sending typing notification without recipient fails
        """
        sender = self.example_email("hamlet")
        result = self.api_post(sender, '/api/v1/typing', {'op': 'start', 'to': '[]'})
        self.assert_json_error(result, 'Missing parameter: \'to\' (recipient)')

    def test_missing_recipient(self) -> None:
        """
        Sending typing notification without recipient fails
        """
        sender = self.example_email("hamlet")
        result = self.api_post(sender, '/api/v1/typing', {'op': 'start'})
        self.assert_json_error(result, "Missing parameter: 'to' (recipient)")

    def test_argument_to_is_not_valid_json(self) -> None:
        """
        Sending typing notification to invalid recipient fails
        """
        sender = self.example_email("hamlet")
        invalid = 'bad email'
        result = self.api_post(sender, '/api/v1/typing', {'op': 'start', 'to': invalid})
        self.assert_json_error(result, "Invalid email 'bad email'")

    def test_bogus_user_id(self) -> None:
        """
        Sending typing notification to invalid recipient fails
        """
        sender = self.example_email("hamlet")
        invalid = '[9999999]'
        result = self.api_post(sender, '/api/v1/typing', {'op': 'start', 'to': invalid})
        self.assert_json_error(result, 'Invalid user ID 9999999')

class TypingHappyPathTest(ZulipTestCase):
    def test_start_to_single_recipient(self) -> None:
        sender = self.example_user('hamlet')
        recipient_user = self.example_user('othello')
        expected_recipients = set([sender, recipient_user])
        expected_recipient_emails = set([user.email for user in expected_recipients])
        expected_recipient_ids = set([user.id for user in expected_recipients])

        params = dict(
            to=ujson.dumps([recipient_user.id]),
            op='start',
        )

        events = []  # type: List[Mapping[str, Any]]
        with queries_captured() as queries:
            with tornado_redirected_to_list(events):
                result = self.api_post(sender.email, '/api/v1/typing', params)

        self.assert_json_success(result)
        self.assertEqual(len(events), 1)
        self.assertEqual(len(queries), 8)

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

    def test_start_to_multiple_recipients(self) -> None:
        sender = self.example_user('hamlet')
        recipient_users = [self.example_user('othello'), self.example_user('cordelia')]
        expected_recipients = set(recipient_users) | set([sender])
        expected_recipient_emails = set([user.email for user in expected_recipients])
        expected_recipient_ids = set([user.id for user in expected_recipients])

        huddle_hash = get_huddle_hash(list(expected_recipient_ids))
        self.assertFalse(Huddle.objects.filter(huddle_hash=huddle_hash).exists())

        events = []  # type: List[Mapping[str, Any]]

        params = dict(
            to=ujson.dumps([user.id for user in recipient_users]),
            op='start',
        )

        with queries_captured() as queries:
            with tornado_redirected_to_list(events):
                result = self.api_post(sender.email, '/api/v1/typing', params)
        self.assert_json_success(result)
        self.assertEqual(len(events), 1)
        self.assertEqual(len(queries), 15)

        # TODO: Fix this somewhat evil side effect of sending
        #       typing indicators.
        self.assertTrue(Huddle.objects.filter(huddle_hash=huddle_hash).exists())

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

    def test_start_to_self(self) -> None:
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

    def test_start_to_another_user(self) -> None:
        """
        Sending typing notification to another user
        is successful.
        """
        sender = self.example_user('hamlet')
        recipient = self.example_user('othello')
        expected_recipients = set([sender, recipient])
        expected_recipient_emails = set([user.email for user in expected_recipients])
        expected_recipient_ids = set([user.id for user in expected_recipients])

        params = dict(
            to=ujson.dumps([recipient.id]),
            op='start'
        )

        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.api_post(sender.email, '/api/v1/typing', params)

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

    def test_stop_to_self(self) -> None:
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
            params = dict(
                to=ujson.dumps([user.id]),
                op='stop'
            )
            result = self.api_post(email, '/api/v1/typing', params)

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

    def test_stop_to_another_user(self) -> None:
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
            params = dict(
                to=ujson.dumps([recipient.id]),
                op='stop'
            )
            result = self.api_post(sender.email, '/api/v1/typing', params)

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
        cross_realm_bot = get_system_bot(settings.WELCOME_BOT)
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

class TypingLegacyMobileSupportTest(ZulipTestCase):
    def test_legacy_email_interface(self) -> None:
        '''
        We are keeping the email interface on life support
        for a couple months until we get some of our
        mobile users upgraded.
        '''
        sender = self.example_user('hamlet')
        othello = self.example_user('othello')
        cordelia = self.example_user('cordelia')

        emails = [othello.email, cordelia.email]

        params = dict(
            to=ujson.dumps(emails),
            op='start',
        )

        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.api_post(sender.email, '/api/v1/typing', params)

        self.assert_json_success(result)
        event = events[0]['event']

        event_recipient_user_ids = {
            user['user_id']
            for user in event['recipients']
        }

        self.assertEqual(
            event_recipient_user_ids,
            {sender.id, othello.id, cordelia.id}
        )
