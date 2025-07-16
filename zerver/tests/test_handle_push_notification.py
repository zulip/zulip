from datetime import timedelta
from unittest import mock

import responses
import time_machine
from django.conf import settings
from django.http.response import ResponseHeaders
from django.test import override_settings
from django.utils.timezone import now
from requests.exceptions import ConnectionError
from requests.models import PreparedRequest
from typing_extensions import override

from analytics.models import RealmCount
from zerver.actions.message_delete import do_delete_messages
from zerver.actions.user_groups import add_subgroups_to_user_group, check_add_user_group
from zerver.actions.user_settings import do_change_user_setting
from zerver.actions.user_topics import do_set_user_topic_visibility_policy
from zerver.lib.push_notifications import (
    UserPushIdentityCompat,
    handle_push_notification,
    handle_remove_push_notification,
)
from zerver.lib.remote_server import PushNotificationBouncerRetryLaterError
from zerver.lib.test_classes import PushNotificationTestCase
from zerver.lib.test_helpers import activate_push_notification_service
from zerver.models import PushDeviceToken, Recipient, UserMessage, UserTopic
from zerver.models.realms import get_realm
from zerver.models.scheduled_jobs import NotificationTriggers
from zerver.models.streams import get_stream
from zilencer.views import DevicesToCleanUpDict

if settings.ZILENCER_ENABLED:
    from zilencer.models import RemotePushDeviceToken


class HandlePushNotificationTest(PushNotificationTestCase):
    DEFAULT_SUBDOMAIN = ""

    def soft_deactivate_main_user(self) -> None:
        self.user_profile = self.example_user("hamlet")
        self.soft_deactivate_user(self.user_profile)

    @override
    def request_callback(self, request: PreparedRequest) -> tuple[int, ResponseHeaders, bytes]:
        assert request.url is not None  # allow mypy to infer url is present.
        assert settings.ZULIP_SERVICES_URL is not None
        local_url = request.url.replace(settings.ZULIP_SERVICES_URL, "")
        assert isinstance(request.body, bytes)
        result = self.uuid_post(
            self.server_uuid, local_url, request.body, content_type="application/json"
        )
        return (result.status_code, result.headers, result.content)

    @activate_push_notification_service()
    @responses.activate
    def test_end_to_end(self) -> None:
        self.add_mock_response()
        self.setup_apns_tokens()
        self.setup_fcm_tokens()

        time_sent = now().replace(microsecond=0)
        with time_machine.travel(time_sent, tick=False):
            message = self.get_message(
                Recipient.PERSONAL,
                type_id=self.personal_recipient_user.id,
                realm_id=self.personal_recipient_user.realm_id,
            )
            UserMessage.objects.create(
                user_profile=self.user_profile,
                message=message,
            )

        time_received = time_sent + timedelta(seconds=1, milliseconds=234)
        missed_message = {
            "message_id": message.id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }
        with (
            time_machine.travel(time_received, tick=False),
            self.mock_fcm() as (
                mock_fcm_app,
                mock_fcm_messaging,
            ),
            self.mock_apns() as (apns_context, send_notification),
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
                return_value=10,
            ),
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as pn_logger,
            self.assertLogs("zilencer.views", level="INFO") as views_logger,
        ):
            apns_devices = list(
                RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.APNS)
                .order_by("id")
                .values_list("token", flat=True)
            )
            fcm_devices = list(
                RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.FCM)
                .order_by("id")
                .values_list("token", flat=True)
            )
            mock_fcm_messaging.send_each.return_value = self.make_fcm_success_response(fcm_devices)
            send_notification.return_value.is_successful = True
            handle_push_notification(self.user_profile.id, missed_message)
            self.assertEqual(
                {
                    (args[0][0].device_token, args[0][0].apns_topic)
                    for args in send_notification.call_args_list
                },
                {
                    (device.token, device.ios_app_id)
                    for device in RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.APNS)
                },
            )
            self.assertEqual(
                views_logger.output,
                [
                    "INFO:zilencer.views:"
                    f"Remote queuing latency for 6cde5f7a-1f7e-4978-9716-49f69ebfc9fe:<id:{self.user_profile.id}><uuid:{self.user_profile.uuid}> "
                    "is 1 seconds",
                    "INFO:zilencer.views:"
                    f"Sending mobile push notifications for remote user 6cde5f7a-1f7e-4978-9716-49f69ebfc9fe:<id:{self.user_profile.id}><uuid:{self.user_profile.uuid}>: "
                    f"{len(fcm_devices)} via FCM devices, {len(apns_devices)} via APNs devices",
                ],
            )
            for token in apns_devices:
                self.assertIn(
                    "INFO:zerver.lib.push_notifications:"
                    f"APNs: Success sending for user <id:{self.user_profile.id}><uuid:{self.user_profile.uuid}> to device {token}",
                    pn_logger.output,
                )
            for idx, token in enumerate(fcm_devices):
                self.assertIn(
                    f"INFO:zerver.lib.push_notifications:FCM: Sent message with ID: {idx} to {token}",
                    pn_logger.output,
                )

            remote_realm_count = RealmCount.objects.values("property", "subgroup", "value").last()
            self.assertEqual(
                remote_realm_count,
                dict(
                    property="mobile_pushes_sent::day",
                    subgroup=None,
                    value=len(fcm_devices) + len(apns_devices),
                ),
            )

    @activate_push_notification_service()
    @responses.activate
    def test_end_to_end_failure_due_to_no_plan(self) -> None:
        self.add_mock_response()

        self.setup_apns_tokens()
        self.setup_fcm_tokens()

        self.server.last_api_feature_level = 237
        self.server.save()

        realm = self.user_profile.realm
        realm.push_notifications_enabled = True
        realm.save()

        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )
        UserMessage.objects.create(
            user_profile=self.user_profile,
            message=message,
        )

        missed_message = {
            "message_id": message.id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }
        with (
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
                return_value=100,
            ) as mock_current_count,
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as pn_logger,
            self.assertLogs("zilencer.views", level="INFO"),
        ):
            handle_push_notification(self.user_profile.id, missed_message)

            self.assertEqual(
                pn_logger.output,
                [
                    f"INFO:zerver.lib.push_notifications:Sending push notifications to mobile clients for user {self.user_profile.id}",
                    "WARNING:zerver.lib.push_notifications:Bouncer refused to send push notification: Your plan doesn't allow sending push notifications. Reason provided by the server: Push notifications access with 10+ users requires signing up for a plan. https://zulip.com/plans/",
                ],
            )
            realm.refresh_from_db()
            self.assertEqual(realm.push_notifications_enabled, False)
            self.assertEqual(realm.push_notifications_enabled_end_timestamp, None)

            # Now verify the flag will correctly get flipped back if the server stops
            # rejecting our notification.

            # This will put us within the allowed number of users to use push notifications
            # for free, so the server will accept our next request.
            mock_current_count.return_value = 5

            new_message_id = self.send_personal_message(
                self.example_user("othello"), self.user_profile
            )
            new_missed_message = {
                "message_id": new_message_id,
                "trigger": NotificationTriggers.DIRECT_MESSAGE,
            }

            handle_push_notification(self.user_profile.id, new_missed_message)
            self.assertIn(
                f"Sent mobile push notifications for user {self.user_profile.id}",
                pn_logger.output[-1],
            )
            realm.refresh_from_db()
            self.assertEqual(realm.push_notifications_enabled, True)
            self.assertEqual(realm.push_notifications_enabled_end_timestamp, None)

    @activate_push_notification_service()
    @responses.activate
    def test_unregistered_client(self) -> None:
        self.add_mock_response()
        self.setup_apns_tokens()
        self.setup_fcm_tokens()

        time_sent = now().replace(microsecond=0)
        with time_machine.travel(time_sent, tick=False):
            message = self.get_message(
                Recipient.PERSONAL,
                type_id=self.personal_recipient_user.id,
                realm_id=self.personal_recipient_user.realm_id,
            )
            UserMessage.objects.create(
                user_profile=self.user_profile,
                message=message,
            )

        time_received = time_sent + timedelta(seconds=1, milliseconds=234)
        missed_message = {
            "message_id": message.id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }
        with (
            time_machine.travel(time_received, tick=False),
            self.mock_fcm() as (
                mock_fcm_app,
                mock_fcm_messaging,
            ),
            self.mock_apns() as (apns_context, send_notification),
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
                return_value=10,
            ),
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as pn_logger,
            self.assertLogs("zilencer.views", level="INFO") as views_logger,
        ):
            apns_devices = list(
                RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.APNS)
                .order_by("id")
                .values_list("token", flat=True)
            )
            fcm_devices = list(
                RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.FCM)
                .order_by("id")
                .values_list("token", flat=True)
            )

            # Reset the local registrations for the user to make them compatible
            # with the RemotePushDeviceToken entries.
            PushDeviceToken.objects.filter(kind=PushDeviceToken.APNS).delete()
            [
                PushDeviceToken.objects.create(
                    kind=PushDeviceToken.APNS,
                    token=device.token,
                    user=self.user_profile,
                    ios_app_id=device.ios_app_id,
                )
                for device in RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.APNS)
            ]
            PushDeviceToken.objects.filter(kind=PushDeviceToken.FCM).delete()
            [
                PushDeviceToken.objects.create(
                    kind=PushDeviceToken.FCM,
                    token=device.token,
                    user=self.user_profile,
                    ios_app_id=device.ios_app_id,
                )
                for device in RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.FCM)
            ]

            mock_fcm_messaging.send_each.return_value = self.make_fcm_success_response(
                [fcm_devices[0]]
            )
            send_notification.return_value.is_successful = False
            send_notification.return_value.description = "Unregistered"

            # Ensure the setup is as expected:
            self.assertNotEqual(
                PushDeviceToken.objects.filter(kind=PushDeviceToken.APNS).count(), 0
            )
            handle_push_notification(self.user_profile.id, missed_message)
            self.assertEqual(
                views_logger.output,
                [
                    "INFO:zilencer.views:"
                    f"Remote queuing latency for 6cde5f7a-1f7e-4978-9716-49f69ebfc9fe:<id:{self.user_profile.id}><uuid:{self.user_profile.uuid}> "
                    "is 1 seconds",
                    "INFO:zilencer.views:"
                    f"Sending mobile push notifications for remote user 6cde5f7a-1f7e-4978-9716-49f69ebfc9fe:<id:{self.user_profile.id}><uuid:{self.user_profile.uuid}>: "
                    f"{len(fcm_devices)} via FCM devices, {len(apns_devices)} via APNs devices",
                ],
            )
            for token in apns_devices:
                self.assertIn(
                    "INFO:zerver.lib.push_notifications:"
                    f"APNs: Removing invalid/expired token {token} (Unregistered)",
                    pn_logger.output,
                )
            self.assertIn(
                "INFO:zerver.lib.push_notifications:Deleting push tokens based on response from bouncer: "
                f"Android: [], Apple: {sorted(apns_devices)}",
                pn_logger.output,
            )
            self.assertEqual(
                RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.APNS).count(), 0
            )
            # Local registrations have also been deleted:
            self.assertEqual(PushDeviceToken.objects.filter(kind=PushDeviceToken.APNS).count(), 0)

    @activate_push_notification_service()
    @responses.activate
    def test_connection_error(self) -> None:
        self.setup_apns_tokens()
        self.setup_fcm_tokens()

        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )
        UserMessage.objects.create(
            user_profile=self.user_profile,
            message=message,
        )

        missed_message = {
            "user_profile_id": self.user_profile.id,
            "message_id": message.id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }
        assert settings.ZULIP_SERVICES_URL is not None
        URL = settings.ZULIP_SERVICES_URL + "/api/v1/remotes/push/notify"
        responses.add(responses.POST, URL, body=ConnectionError())
        with self.assertRaises(PushNotificationBouncerRetryLaterError):
            handle_push_notification(self.user_profile.id, missed_message)

    @mock.patch("zerver.lib.push_notifications.push_notifications_configured", return_value=True)
    @override_settings(ZULIP_SERVICE_PUSH_NOTIFICATIONS=False, ZULIP_SERVICES=set())
    def test_read_message(self, mock_push_notifications: mock.MagicMock) -> None:
        user_profile = self.example_user("hamlet")
        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )

        usermessage = UserMessage.objects.create(
            user_profile=user_profile,
            message=message,
        )

        missed_message = {
            "message_id": message.id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }

        # If the message is unread, we should send push notifications.
        with (
            mock.patch(
                "zerver.lib.push_notifications.send_apple_push_notification", return_value=1
            ) as mock_send_apple,
            mock.patch(
                "zerver.lib.push_notifications.send_android_push_notification", return_value=1
            ) as mock_send_android,
        ):
            handle_push_notification(user_profile.id, missed_message)
        mock_send_apple.assert_called_once()
        mock_send_android.assert_called_once()

        # If the message has been read, don't send push notifications.
        usermessage.flags.read = True
        usermessage.save()
        with (
            mock.patch(
                "zerver.lib.push_notifications.send_apple_push_notification", return_value=1
            ) as mock_send_apple,
            mock.patch(
                "zerver.lib.push_notifications.send_android_push_notification", return_value=1
            ) as mock_send_android,
        ):
            handle_push_notification(user_profile.id, missed_message)
        mock_send_apple.assert_not_called()
        mock_send_android.assert_not_called()

    def test_deleted_message(self) -> None:
        """Simulates the race where message is deleted before handling push notifications"""
        user_profile = self.example_user("hamlet")
        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )
        UserMessage.objects.create(
            user_profile=user_profile,
            flags=UserMessage.flags.read,
            message=message,
        )
        missed_message = {
            "message_id": message.id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }
        # Now, delete the message the normal way
        do_delete_messages(user_profile.realm, [message], acting_user=None)

        # This mock.patch() should be assertNoLogs once that feature
        # is added to Python.
        with (
            mock.patch("zerver.lib.push_notifications.uses_notification_bouncer") as mock_check,
            mock.patch("logging.error") as mock_logging_error,
            mock.patch(
                "zerver.lib.push_notifications.push_notifications_configured", return_value=True
            ) as mock_push_notifications,
        ):
            handle_push_notification(user_profile.id, missed_message)
            mock_push_notifications.assert_called_once()
            # Check we didn't proceed through and didn't log anything.
            mock_check.assert_not_called()
            mock_logging_error.assert_not_called()

    def test_missing_message(self) -> None:
        """Simulates the race where message is missing when handling push notifications"""
        user_profile = self.example_user("hamlet")
        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )
        UserMessage.objects.create(
            user_profile=user_profile,
            flags=UserMessage.flags.read,
            message=message,
        )
        missed_message = {
            "message_id": message.id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }
        # Now delete the message forcefully, so it just doesn't exist.
        message.delete()

        # This should log an error
        with (
            mock.patch("zerver.lib.push_notifications.uses_notification_bouncer") as mock_check,
            self.assertLogs(level="INFO") as mock_logging_info,
            mock.patch(
                "zerver.lib.push_notifications.push_notifications_configured", return_value=True
            ) as mock_push_notifications,
        ):
            handle_push_notification(user_profile.id, missed_message)
            mock_push_notifications.assert_called_once()
            # Check we didn't proceed through.
            mock_check.assert_not_called()
            self.assertEqual(
                mock_logging_info.output,
                [
                    f"INFO:root:Unexpected message access failure handling push notifications: {user_profile.id} {missed_message['message_id']}"
                ],
            )

    def test_send_notifications_to_bouncer(self) -> None:
        self.setup_apns_tokens()
        self.setup_fcm_tokens()

        user_profile = self.user_profile
        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )
        UserMessage.objects.create(
            user_profile=user_profile,
            message=message,
        )

        missed_message = {
            "message_id": message.id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }
        with (
            activate_push_notification_service(),
            mock.patch(
                "zerver.lib.push_notifications.get_message_payload_apns",
                return_value={"apns": True},
            ),
            mock.patch(
                "zerver.lib.push_notifications.get_message_payload_gcm",
                return_value=({"gcm": True}, {}),
            ),
            mock.patch(
                "zerver.lib.push_notifications.send_json_to_push_bouncer",
                return_value=dict(
                    total_android_devices=3,
                    total_apple_devices=5,
                    deleted_devices=DevicesToCleanUpDict(android_devices=[], apple_devices=[]),
                    realm=None,
                ),
            ) as mock_send,
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as mock_logging_info,
        ):
            handle_push_notification(user_profile.id, missed_message)
            mock_send.assert_called_with(
                "POST",
                "push/notify",
                {
                    "user_uuid": str(user_profile.uuid),
                    "user_id": user_profile.id,
                    "realm_uuid": str(user_profile.realm.uuid),
                    "apns_payload": {"apns": True},
                    "gcm_payload": {"gcm": True},
                    "gcm_options": {},
                    "android_devices": list(
                        PushDeviceToken.objects.filter(user=user_profile, kind=PushDeviceToken.FCM)
                        .order_by("id")
                        .values_list("token", flat=True)
                    ),
                    "apple_devices": list(
                        PushDeviceToken.objects.filter(user=user_profile, kind=PushDeviceToken.APNS)
                        .order_by("id")
                        .values_list("token", flat=True)
                    ),
                },
            )

            self.assertEqual(
                mock_logging_info.output,
                [
                    f"INFO:zerver.lib.push_notifications:Sending push notifications to mobile clients for user {user_profile.id}",
                    f"INFO:zerver.lib.push_notifications:Sent mobile push notifications for user {user_profile.id} through bouncer: 3 via FCM devices, 5 via APNs devices",
                ],
            )

    def test_non_bouncer_push(self) -> None:
        self.setup_apns_tokens()
        self.setup_fcm_tokens()
        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )
        UserMessage.objects.create(
            user_profile=self.user_profile,
            message=message,
        )

        android_devices = list(
            PushDeviceToken.objects.filter(user=self.user_profile, kind=PushDeviceToken.FCM)
        )

        apple_devices = list(
            PushDeviceToken.objects.filter(user=self.user_profile, kind=PushDeviceToken.APNS)
        )

        missed_message = {
            "message_id": message.id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }
        with (
            mock.patch(
                "zerver.lib.push_notifications.get_message_payload_apns",
                return_value={"apns": True},
            ),
            mock.patch(
                "zerver.lib.push_notifications.get_message_payload_gcm",
                return_value=({"gcm": True}, {}),
            ),
            mock.patch(
                # Simulate the send...push_notification functions returning a number of successes
                # lesser than the number of devices, so that we can verify correct CountStat counting.
                "zerver.lib.push_notifications.send_apple_push_notification",
                return_value=len(apple_devices) - 1,
            ) as mock_send_apple,
            mock.patch(
                "zerver.lib.push_notifications.send_android_push_notification",
                return_value=len(android_devices) - 1,
            ) as mock_send_android,
            mock.patch(
                "zerver.lib.push_notifications.push_notifications_configured", return_value=True
            ) as mock_push_notifications,
        ):
            handle_push_notification(self.user_profile.id, missed_message)
            user_identity = UserPushIdentityCompat(user_id=self.user_profile.id)
            mock_send_apple.assert_called_with(user_identity, apple_devices, {"apns": True})
            mock_send_android.assert_called_with(user_identity, android_devices, {"gcm": True}, {})
            mock_push_notifications.assert_called_once()

        remote_realm_count = RealmCount.objects.values("property", "subgroup", "value").last()
        self.assertEqual(
            remote_realm_count,
            dict(
                property="mobile_pushes_sent::day",
                subgroup=None,
                value=len(android_devices) + len(apple_devices) - 2,
            ),
        )

    def test_send_remove_notifications_to_bouncer(self) -> None:
        self.setup_apns_tokens()
        self.setup_fcm_tokens()

        user_profile = self.user_profile
        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )
        UserMessage.objects.create(
            user_profile=user_profile,
            message=message,
            flags=UserMessage.flags.active_mobile_push_notification,
        )

        with (
            activate_push_notification_service(),
            mock.patch("zerver.lib.push_notifications.send_notifications_to_bouncer") as mock_send,
        ):
            handle_remove_push_notification(user_profile.id, [message.id])
            mock_send.assert_called_with(
                user_profile,
                {
                    "badge": 0,
                    "custom": {
                        "zulip": {
                            "server": "testserver",
                            "realm_id": self.sender.realm.id,
                            "realm_name": self.sender.realm.name,
                            "realm_uri": "http://zulip.testserver",
                            "realm_url": "http://zulip.testserver",
                            "user_id": self.user_profile.id,
                            "event": "remove",
                            "zulip_message_ids": str(message.id),
                        },
                    },
                },
                {
                    "server": "testserver",
                    "realm_id": self.sender.realm.id,
                    "realm_name": self.sender.realm.name,
                    "realm_uri": "http://zulip.testserver",
                    "realm_url": "http://zulip.testserver",
                    "user_id": self.user_profile.id,
                    "event": "remove",
                    "zulip_message_ids": str(message.id),
                    "zulip_message_id": message.id,
                },
                {"priority": "normal"},
                list(
                    PushDeviceToken.objects.filter(
                        user=user_profile, kind=PushDeviceToken.FCM
                    ).order_by("id")
                ),
                list(
                    PushDeviceToken.objects.filter(
                        user=user_profile, kind=PushDeviceToken.APNS
                    ).order_by("id")
                ),
            )
            user_message = UserMessage.objects.get(user_profile=self.user_profile, message=message)
            self.assertEqual(user_message.flags.active_mobile_push_notification, False)

    def test_non_bouncer_push_remove(self) -> None:
        self.setup_apns_tokens()
        self.setup_fcm_tokens()
        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )
        UserMessage.objects.create(
            user_profile=self.user_profile,
            message=message,
            flags=UserMessage.flags.active_mobile_push_notification,
        )

        android_devices = list(
            PushDeviceToken.objects.filter(user=self.user_profile, kind=PushDeviceToken.FCM)
        )

        apple_devices = list(
            PushDeviceToken.objects.filter(user=self.user_profile, kind=PushDeviceToken.APNS)
        )

        with (
            mock.patch(
                "zerver.lib.push_notifications.push_notifications_configured", return_value=True
            ) as mock_push_notifications,
            mock.patch(
                # Simulate the send...push_notification functions returning a number of successes
                # lesser than the number of devices, so that we can verify correct CountStat counting.
                "zerver.lib.push_notifications.send_android_push_notification",
                return_value=len(apple_devices) - 1,
            ) as mock_send_android,
            mock.patch(
                "zerver.lib.push_notifications.send_apple_push_notification",
                return_value=len(apple_devices) - 1,
            ) as mock_send_apple,
        ):
            handle_remove_push_notification(self.user_profile.id, [message.id])
            mock_push_notifications.assert_called_once()
            user_identity = UserPushIdentityCompat(user_id=self.user_profile.id)
            mock_send_android.assert_called_with(
                user_identity,
                android_devices,
                {
                    "server": "testserver",
                    "realm_id": self.sender.realm.id,
                    "realm_name": self.sender.realm.name,
                    "realm_uri": "http://zulip.testserver",
                    "realm_url": "http://zulip.testserver",
                    "user_id": self.user_profile.id,
                    "event": "remove",
                    "zulip_message_ids": str(message.id),
                    "zulip_message_id": message.id,
                },
                {"priority": "normal"},
            )
            mock_send_apple.assert_called_with(
                user_identity,
                apple_devices,
                {
                    "badge": 0,
                    "custom": {
                        "zulip": {
                            "server": "testserver",
                            "realm_id": self.sender.realm.id,
                            "realm_name": self.sender.realm.name,
                            "realm_uri": "http://zulip.testserver",
                            "realm_url": "http://zulip.testserver",
                            "user_id": self.user_profile.id,
                            "event": "remove",
                            "zulip_message_ids": str(message.id),
                        }
                    },
                },
            )
            user_message = UserMessage.objects.get(user_profile=self.user_profile, message=message)
            self.assertEqual(user_message.flags.active_mobile_push_notification, False)

            remote_realm_count = RealmCount.objects.values("property", "subgroup", "value").last()
            self.assertEqual(
                remote_realm_count,
                dict(
                    property="mobile_pushes_sent::day",
                    subgroup=None,
                    value=len(android_devices) + len(apple_devices) - 2,
                ),
            )

    def test_user_message_does_not_exist(self) -> None:
        """This simulates a condition that should only be an error if the user is
        not long-term idle; we fake it, though, in the sense that the user should
        not have received the message in the first place"""
        self.make_stream("public_stream")
        sender = self.example_user("iago")
        self.subscribe(sender, "public_stream")
        message_id = self.send_stream_message(sender, "public_stream", "test")
        missed_message = {"message_id": message_id}
        with (
            self.assertLogs("zerver.lib.push_notifications", level="ERROR") as logger,
            mock.patch(
                "zerver.lib.push_notifications.push_notifications_configured", return_value=True
            ) as mock_push_notifications,
        ):
            handle_push_notification(self.user_profile.id, missed_message)
            self.assertEqual(
                "ERROR:zerver.lib.push_notifications:"
                f"Could not find UserMessage with message_id {message_id} and user_id {self.user_profile.id}",
                logger.output[0],
            )
            mock_push_notifications.assert_called_once()

    def test_user_message_does_not_exist_remove(self) -> None:
        """This simulates a condition that should only be an error if the user is
        not long-term idle; we fake it, though, in the sense that the user should
        not have received the message in the first place"""
        self.setup_apns_tokens()
        self.setup_fcm_tokens()
        self.make_stream("public_stream")
        sender = self.example_user("iago")
        self.subscribe(sender, "public_stream")
        message_id = self.send_stream_message(sender, "public_stream", "test")
        with (
            mock.patch(
                "zerver.lib.push_notifications.push_notifications_configured", return_value=True
            ) as mock_push_notifications,
            mock.patch(
                "zerver.lib.push_notifications.send_android_push_notification", return_value=1
            ) as mock_send_android,
            mock.patch(
                "zerver.lib.push_notifications.send_apple_push_notification", return_value=1
            ) as mock_send_apple,
        ):
            handle_remove_push_notification(self.user_profile.id, [message_id])
            mock_push_notifications.assert_called_once()
            mock_send_android.assert_called_once()
            mock_send_apple.assert_called_once()

    def test_user_message_soft_deactivated(self) -> None:
        """This simulates a condition that should only be an error if the user is
        not long-term idle; we fake it, though, in the sense that the user should
        not have received the message in the first place"""
        self.setup_apns_tokens()
        self.setup_fcm_tokens()
        self.make_stream("public_stream")
        sender = self.example_user("iago")
        self.subscribe(self.user_profile, "public_stream")
        self.subscribe(sender, "public_stream")
        logger_string = "zulip.soft_deactivation"
        with self.assertLogs(logger_string, level="INFO") as info_logs:
            self.soft_deactivate_main_user()

        self.assertEqual(
            info_logs.output,
            [
                f"INFO:{logger_string}:Soft deactivated user {self.user_profile.id}",
                f"INFO:{logger_string}:Soft-deactivated batch of 1 users; 0 remain to process",
            ],
        )
        message_id = self.send_stream_message(sender, "public_stream", "test")
        missed_message = {
            "message_id": message_id,
            "trigger": NotificationTriggers.STREAM_PUSH,
        }

        android_devices = list(
            PushDeviceToken.objects.filter(user=self.user_profile, kind=PushDeviceToken.FCM)
        )

        apple_devices = list(
            PushDeviceToken.objects.filter(user=self.user_profile, kind=PushDeviceToken.APNS)
        )

        with (
            mock.patch(
                "zerver.lib.push_notifications.get_message_payload_apns",
                return_value={"apns": True},
            ),
            mock.patch(
                "zerver.lib.push_notifications.get_message_payload_gcm",
                return_value=({"gcm": True}, {}),
            ),
            mock.patch(
                "zerver.lib.push_notifications.send_apple_push_notification", return_value=1
            ) as mock_send_apple,
            mock.patch(
                "zerver.lib.push_notifications.send_android_push_notification", return_value=1
            ) as mock_send_android,
            mock.patch("zerver.lib.push_notifications.logger.error") as mock_logger,
            mock.patch(
                "zerver.lib.push_notifications.push_notifications_configured", return_value=True
            ) as mock_push_notifications,
        ):
            handle_push_notification(self.user_profile.id, missed_message)
            mock_logger.assert_not_called()
            user_identity = UserPushIdentityCompat(user_id=self.user_profile.id)
            mock_send_apple.assert_called_with(user_identity, apple_devices, {"apns": True})
            mock_send_android.assert_called_with(user_identity, android_devices, {"gcm": True}, {})
            mock_push_notifications.assert_called_once()

    @override_settings(MAX_GROUP_SIZE_FOR_MENTION_REACTIVATION=2)
    @mock.patch("zerver.lib.push_notifications.push_notifications_configured", return_value=True)
    def test_user_push_soft_reactivate_soft_deactivated_user(
        self, mock_push_notifications: mock.MagicMock
    ) -> None:
        othello = self.example_user("othello")
        cordelia = self.example_user("cordelia")
        zulip_realm = get_realm("zulip")

        # user groups having upto 'MAX_GROUP_SIZE_FOR_MENTION_REACTIVATION'
        # members are small user groups.
        small_user_group = check_add_user_group(
            zulip_realm,
            "small_user_group",
            [self.user_profile, othello],
            acting_user=othello,
        )

        large_user_group = check_add_user_group(
            zulip_realm, "large_user_group", [self.user_profile], acting_user=othello
        )
        subgroup = check_add_user_group(
            zulip_realm, "subgroup", [othello, cordelia], acting_user=othello
        )
        add_subgroups_to_user_group(large_user_group, [subgroup], acting_user=None)

        # Personal mention in a stream message should soft reactivate the user
        def mention_in_stream() -> None:
            mention = f"@**{self.user_profile.full_name}**"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_push_notification(
                self.user_profile.id,
                {
                    "message_id": stream_mentioned_message_id,
                    "trigger": NotificationTriggers.MENTION,
                },
            )

        self.soft_deactivate_main_user()
        self.expect_soft_reactivation(self.user_profile, mention_in_stream)

        # Direct message should soft reactivate the user
        def direct_message() -> None:
            # Soft reactivate the user by sending a personal message
            personal_message_id = self.send_personal_message(othello, self.user_profile, "Message")
            handle_push_notification(
                self.user_profile.id,
                {
                    "message_id": personal_message_id,
                    "trigger": NotificationTriggers.DIRECT_MESSAGE,
                },
            )

        self.soft_deactivate_main_user()
        self.expect_soft_reactivation(self.user_profile, direct_message)

        # User FOLLOWS the topic.
        # 'wildcard_mentions_notify' is disabled to verify the corner case when only
        # 'enable_followed_topic_wildcard_mentions_notify' is enabled (True by default).
        do_set_user_topic_visibility_policy(
            self.user_profile,
            get_stream("Denmark", self.user_profile.realm),
            "test",
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )
        do_change_user_setting(
            self.user_profile, "wildcard_mentions_notify", False, acting_user=None
        )

        # Topic wildcard mention in followed topic should soft reactivate the user
        # user should be a topic participant
        self.send_stream_message(self.user_profile, "Denmark", "topic participant")

        def send_topic_wildcard_mention() -> None:
            mention = "@**topic**"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_push_notification(
                self.user_profile.id,
                {
                    "message_id": stream_mentioned_message_id,
                    "trigger": NotificationTriggers.TOPIC_WILDCARD_MENTION_IN_FOLLOWED_TOPIC,
                },
            )

        self.soft_deactivate_main_user()
        self.expect_soft_reactivation(self.user_profile, send_topic_wildcard_mention)

        # Stream wildcard mention in followed topic should NOT soft reactivate the user
        def send_stream_wildcard_mention() -> None:
            mention = "@**all**"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_push_notification(
                self.user_profile.id,
                {
                    "message_id": stream_mentioned_message_id,
                    "trigger": NotificationTriggers.STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC,
                },
            )

        self.soft_deactivate_main_user()
        self.expect_to_stay_long_term_idle(self.user_profile, send_stream_wildcard_mention)

        # Reset
        do_set_user_topic_visibility_policy(
            self.user_profile,
            get_stream("Denmark", self.user_profile.realm),
            "test",
            visibility_policy=UserTopic.VisibilityPolicy.INHERIT,
        )
        do_change_user_setting(
            self.user_profile, "wildcard_mentions_notify", True, acting_user=None
        )

        # Topic Wildcard mention should soft reactivate the user
        self.expect_soft_reactivation(self.user_profile, send_topic_wildcard_mention)

        # Stream Wildcard mention should NOT soft reactivate the user
        self.soft_deactivate_main_user()
        self.expect_to_stay_long_term_idle(self.user_profile, send_stream_wildcard_mention)

        # Small group mention should soft reactivate the user
        def send_small_group_mention() -> None:
            mention = "@*small_user_group*"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_push_notification(
                self.user_profile.id,
                {
                    "message_id": stream_mentioned_message_id,
                    "trigger": NotificationTriggers.MENTION,
                    "mentioned_user_group_id": small_user_group.id,
                },
            )

        self.soft_deactivate_main_user()
        self.expect_soft_reactivation(self.user_profile, send_small_group_mention)

        # Large group mention should NOT soft reactivate the user
        def send_large_group_mention() -> None:
            mention = "@*large_user_group*"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_push_notification(
                self.user_profile.id,
                {
                    "message_id": stream_mentioned_message_id,
                    "trigger": NotificationTriggers.MENTION,
                    "mentioned_user_group_id": large_user_group.id,
                },
            )

        self.soft_deactivate_main_user()
        self.expect_to_stay_long_term_idle(self.user_profile, send_large_group_mention)

    @mock.patch("zerver.lib.push_notifications.logger.info")
    @mock.patch("zerver.lib.push_notifications.push_notifications_configured", return_value=True)
    def test_user_push_notification_already_active(
        self, mock_push_notifications: mock.MagicMock, mock_info: mock.MagicMock
    ) -> None:
        user_profile = self.example_user("hamlet")
        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )
        UserMessage.objects.create(
            user_profile=user_profile,
            flags=UserMessage.flags.active_mobile_push_notification,
            message=message,
        )

        missed_message = {
            "message_id": message.id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }
        handle_push_notification(user_profile.id, missed_message)
        mock_push_notifications.assert_called_once()
        # Check we didn't proceed ahead and function returned.
        mock_info.assert_not_called()
