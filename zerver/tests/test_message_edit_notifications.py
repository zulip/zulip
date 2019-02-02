# -*- coding: utf-8 -*-

from typing import Any, Dict, Mapping, Union

import mock

from django.utils.timezone import now as timezone_now

from zerver.lib.actions import (
    get_client,
)

from zerver.lib.test_classes import (
    ZulipTestCase,
)

from zerver.models import (
    get_stream_recipient,
    Subscription,
    UserPresence,
)

from zerver.tornado.event_queue import (
    maybe_enqueue_notifications,
)

class EditMessageSideEffectsTest(ZulipTestCase):
    def _assert_update_does_not_notify_anybody(self, message_id: int, content: str) -> None:
        url = '/json/messages/' + str(message_id)

        request = dict(
            message_id=message_id,
            content=content,
        )

        with mock.patch('zerver.tornado.event_queue.maybe_enqueue_notifications') as m:
            result = self.client_patch(url, request)

        self.assert_json_success(result)
        self.assertFalse(m.called)

    def test_updates_with_pm_mention(self) -> None:
        hamlet = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')

        self.login(hamlet.email)

        message_id = self.send_personal_message(
            hamlet.email,
            cordelia.email,
            content='no mention'
        )

        self._assert_update_does_not_notify_anybody(
            message_id=message_id,
            content='now we mention @**Cordelia Lear**',
        )

    def _login_and_send_original_stream_message(self, content: str) -> int:
        '''
            Note our conventions here:

                Hamlet is our logged in user (and sender).
                Cordelia is the receiver we care about.
                Scotland is the stream we send messages to.
        '''
        hamlet = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')

        self.login(hamlet.email)
        self.subscribe(hamlet, 'Scotland')
        self.subscribe(cordelia, 'Scotland')

        message_id = self.send_stream_message(
            hamlet.email,
            'Scotland',
            content=content,
        )

        return message_id

    def _get_queued_data_for_message_update(self, message_id: int, content: str,
                                            expect_short_circuit: bool=False) -> Dict[str, Any]:
        '''
        This function updates a message with a post to
        /json/messages/(message_id).

        By using mocks, we are able to capture two pieces of data:

            enqueue_kwargs: These are the arguments passed in to
                            maybe_enqueue_notifications.

            queue_messages: These are the messages that
                            maybe_enqueue_notifications actually
                            puts on the queue.

        Using this helper allows you to construct a test that goes
        pretty deep into the missed-messages codepath, without actually
        queuing the final messages.
        '''
        url = '/json/messages/' + str(message_id)

        request = dict(
            message_id=message_id,
            content=content,
        )

        with mock.patch('zerver.tornado.event_queue.maybe_enqueue_notifications') as m:
            result = self.client_patch(url, request)

        cordelia = self.example_user('cordelia')
        cordelia_calls = [
            call_args
            for call_args in m.call_args_list
            if call_args[1]['user_profile_id'] == cordelia.id
        ]

        if expect_short_circuit:
            self.assertEqual(len(cordelia_calls), 0)
            return {}

        # Normally we expect maybe_enqueue_notifications to be
        # called for Cordelia, so continue on.
        self.assertEqual(len(cordelia_calls), 1)
        enqueue_kwargs = cordelia_calls[0][1]

        queue_messages = []

        def fake_publish(queue_name: str,
                         event: Union[Mapping[str, Any], str],
                         *args: Any) -> None:
            queue_messages.append(dict(
                queue_name=queue_name,
                event=event,
            ))

        with mock.patch('zerver.tornado.event_queue.queue_json_publish') as m:
            m.side_effect = fake_publish
            maybe_enqueue_notifications(**enqueue_kwargs)

        self.assert_json_success(result)

        return dict(
            enqueue_kwargs=enqueue_kwargs,
            queue_messages=queue_messages
        )

    def test_updates_with_stream_mention(self) -> None:
        message_id = self._login_and_send_original_stream_message(
            content='no mention',
        )

        info = self._get_queued_data_for_message_update(
            message_id=message_id,
            content='now we mention @**Cordelia Lear**',
        )

        cordelia = self.example_user('cordelia')
        expected_enqueue_kwargs = dict(
            user_profile_id=cordelia.id,
            message_id=message_id,
            private_message=False,
            mentioned=True,
            stream_push_notify=False,
            stream_email_notify=False,
            stream_name='Scotland',
            always_push_notify=False,
            idle=True,
            already_notified={},
        )

        self.assertEqual(info['enqueue_kwargs'], expected_enqueue_kwargs)

        queue_messages = info['queue_messages']

        self.assertEqual(len(queue_messages), 2)

        self.assertEqual(queue_messages[0]['queue_name'], 'missedmessage_mobile_notifications')
        mobile_event = queue_messages[0]['event']

        self.assertEqual(mobile_event['user_profile_id'], cordelia.id)
        self.assertEqual(mobile_event['trigger'], 'mentioned')

        self.assertEqual(queue_messages[1]['queue_name'], 'missedmessage_emails')
        email_event = queue_messages[1]['event']

        self.assertEqual(email_event['user_profile_id'], cordelia.id)
        self.assertEqual(email_event['trigger'], 'mentioned')

    def test_second_mention_is_ignored(self) -> None:
        message_id = self._login_and_send_original_stream_message(
            content='hello @**Cordelia Lear**'
        )

        self._get_queued_data_for_message_update(
            message_id=message_id,
            content='re-mention @**Cordelia Lear**',
            expect_short_circuit=True,
        )

    def _turn_on_stream_push_for_cordelia(self) -> None:
        '''
        conventions:
            Cordelia is the message receiver we care about.
            Scotland is our stream.
        '''
        cordelia = self.example_user('cordelia')
        stream = self.subscribe(cordelia, 'Scotland')
        recipient = get_stream_recipient(stream.id)
        cordelia_subscription = Subscription.objects.get(
            user_profile_id=cordelia.id,
            recipient=recipient,
        )
        cordelia_subscription.push_notifications = True
        cordelia_subscription.save()

    def test_updates_with_stream_push_notify(self) -> None:
        self._turn_on_stream_push_for_cordelia()

        message_id = self._login_and_send_original_stream_message(
            content='no mention'
        )

        # Even though Cordelia configured this stream for pushes,
        # we short-ciruit the logic, assuming the original message
        # also did a push.
        self._get_queued_data_for_message_update(
            message_id=message_id,
            content='nothing special about updated message',
            expect_short_circuit=True,
        )

    def _cordelia_connected_to_zulip(self) -> Any:
        '''
        Right now the easiest way to make Cordelia look
        connected to Zulip is to mock the function below.

        This is a bit blunt, as it affects other users too,
        but we only really look at Cordelia's data, anyway.
        '''
        return mock.patch(
            'zerver.tornado.event_queue.receiver_is_off_zulip',
            return_value=False
        )

    def test_stream_push_notify_for_sorta_present_user(self) -> None:
        self._turn_on_stream_push_for_cordelia()

        message_id = self._login_and_send_original_stream_message(
            content='no mention'
        )

        # Simulate Cordelia still has an actively polling client, but
        # the lack of presence info should still mark her as offline.
        #
        # Despite Cordelia being offline, we still short circuit
        # offline notifications due to the her stream push setting.
        with self._cordelia_connected_to_zulip():
            self._get_queued_data_for_message_update(
                message_id=message_id,
                content='nothing special about updated message',
                expect_short_circuit=True,
            )

    def _make_cordelia_present_on_web(self) -> None:
        cordelia = self.example_user('cordelia')
        UserPresence.objects.create(
            user_profile_id=cordelia.id,
            status=UserPresence.ACTIVE,
            client=get_client('web'),
            timestamp=timezone_now(),
        )

    def test_stream_push_notify_for_fully_present_user(self) -> None:
        self._turn_on_stream_push_for_cordelia()

        message_id = self._login_and_send_original_stream_message(
            content='no mention'
        )

        self._make_cordelia_present_on_web()

        # Simulate Cordelia is FULLY present, not just in term of
        # browser activity, but also in terms of her client descriptors.
        with self._cordelia_connected_to_zulip():
            self._get_queued_data_for_message_update(
                message_id=message_id,
                content='nothing special about updated message',
                expect_short_circuit=True,
            )

    def test_always_push_notify_for_fully_present_mentioned_user(self) -> None:
        cordelia = self.example_user('cordelia')
        cordelia.enable_online_push_notifications = True
        cordelia.save()

        message_id = self._login_and_send_original_stream_message(
            content='no mention'
        )

        self._make_cordelia_present_on_web()

        # Simulate Cordelia is FULLY present, not just in term of
        # browser activity, but also in terms of her client descriptors.
        with self._cordelia_connected_to_zulip():
            info = self._get_queued_data_for_message_update(
                message_id=message_id,
                content='newly mention @**Cordelia Lear**',
            )

        expected_enqueue_kwargs = dict(
            user_profile_id=cordelia.id,
            message_id=message_id,
            private_message=False,
            mentioned=True,
            stream_push_notify=False,
            stream_email_notify=False,
            stream_name='Scotland',
            always_push_notify=True,
            idle=False,
            already_notified={},
        )

        self.assertEqual(info['enqueue_kwargs'], expected_enqueue_kwargs)

        queue_messages = info['queue_messages']

        self.assertEqual(len(queue_messages), 1)

    def test_always_push_notify_for_fully_present_boring_user(self) -> None:
        cordelia = self.example_user('cordelia')
        cordelia.enable_online_push_notifications = True
        cordelia.save()

        message_id = self._login_and_send_original_stream_message(
            content='no mention'
        )

        self._make_cordelia_present_on_web()

        # Simulate Cordelia is FULLY present, not just in term of
        # browser activity, but also in terms of her client descriptors.
        with self._cordelia_connected_to_zulip():
            info = self._get_queued_data_for_message_update(
                message_id=message_id,
                content='nothing special about updated message',
            )

        expected_enqueue_kwargs = dict(
            user_profile_id=cordelia.id,
            message_id=message_id,
            private_message=False,
            mentioned=False,
            stream_push_notify=False,
            stream_email_notify=False,
            stream_name='Scotland',
            always_push_notify=True,
            idle=False,
            already_notified={},
        )

        self.assertEqual(info['enqueue_kwargs'], expected_enqueue_kwargs)

        queue_messages = info['queue_messages']

        # Even though Cordelia has enable_online_push_notifications set
        # to True, we don't send her any offline notifications, since she
        # was not mentioned.
        self.assertEqual(len(queue_messages), 0)

    def test_updates_with_stream_mention_of_sorta_present_user(self) -> None:
        cordelia = self.example_user('cordelia')

        message_id = self._login_and_send_original_stream_message(
            content='no mention'
        )

        # We will simulate that the user still has a an active client,
        # but they don't have UserPresence rows, so we will still
        # send offline notifications.
        with self._cordelia_connected_to_zulip():
            info = self._get_queued_data_for_message_update(
                message_id=message_id,
                content='now we mention @**Cordelia Lear**',
            )

        expected_enqueue_kwargs = dict(
            user_profile_id=cordelia.id,
            message_id=message_id,
            private_message=False,
            mentioned=True,
            stream_push_notify=False,
            stream_email_notify=False,
            stream_name='Scotland',
            always_push_notify=False,
            idle=True,
            already_notified={},
        )
        self.assertEqual(info['enqueue_kwargs'], expected_enqueue_kwargs)

        # She will get messages enqueued.  (Other tests drill down on the
        # actual content of these messages.)
        self.assertEqual(len(info['queue_messages']), 2)

    def test_updates_with_stream_mention_of_fully_present_user(self) -> None:
        cordelia = self.example_user('cordelia')

        message_id = self._login_and_send_original_stream_message(
            content='no mention'
        )

        self._make_cordelia_present_on_web()

        # Simulate Cordelia is FULLY present, not just in term of
        # browser activity, but also in terms of her client descriptors.
        with self._cordelia_connected_to_zulip():
            info = self._get_queued_data_for_message_update(
                message_id=message_id,
                content='now we mention @**Cordelia Lear**',
            )

        expected_enqueue_kwargs = dict(
            user_profile_id=cordelia.id,
            message_id=message_id,
            private_message=False,
            mentioned=True,
            stream_push_notify=False,
            stream_email_notify=False,
            stream_name='Scotland',
            always_push_notify=False,
            idle=False,
            already_notified={},
        )
        self.assertEqual(info['enqueue_kwargs'], expected_enqueue_kwargs)

        # Because Cordelia is FULLY present, we don't need to send any offline
        # push notifications or missed message emails.
        self.assertEqual(len(info['queue_messages']), 0)
