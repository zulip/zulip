from datetime import datetime, timezone
from unittest import mock

import responses
import time_machine
from django.test import override_settings
from django.utils.timezone import now
from firebase_admin.exceptions import InternalError
from firebase_admin.messaging import UnregisteredError

from analytics.models import RealmCount
from zerver.actions.user_groups import check_add_user_group
from zerver.lib.avatar import absolute_avatar_url
from zerver.lib.exceptions import MissingRemoteRealmError
from zerver.lib.push_notifications import (
    PushNotificationsDisallowedByBouncerError,
    handle_push_notification,
    handle_remove_push_notification,
)
from zerver.lib.remote_server import (
    PushNotificationBouncerError,
    PushNotificationBouncerRetryLaterError,
    PushNotificationBouncerServerError,
)
from zerver.lib.test_classes import E2EEPushNotificationTestCase
from zerver.lib.test_helpers import activate_push_notification_service
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import PushDevice, UserMessage
from zerver.models.realms import get_realm
from zerver.models.scheduled_jobs import NotificationTriggers
from zilencer.lib.push_notifications import SentPushNotificationResult
from zilencer.models import RemoteRealm, RemoteRealmCount


@activate_push_notification_service()
class SendPushNotificationTest(E2EEPushNotificationTestCase):
    def test_success_cloud(self) -> None:
        hamlet = self.example_user("hamlet")
        aaron = self.example_user("aaron")

        registered_device_apple, registered_device_android = (
            self.register_push_devices_for_notification()
        )
        message_id = self.send_personal_message(
            from_user=aaron, to_user=hamlet, skip_capture_on_commit_callbacks=True
        )
        missed_message = {
            "message_id": message_id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }

        self.assertEqual(RealmCount.objects.count(), 0)

        with (
            self.mock_fcm() as mock_fcm_messaging,
            self.mock_apns() as send_notification,
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as zerver_logger,
            self.assertLogs("zilencer.lib.push_notifications", level="INFO") as zilencer_logger,
            mock.patch("time.perf_counter", side_effect=[10.0, 15.0]),
        ):
            mock_fcm_messaging.send_each.return_value = self.make_fcm_success_response()
            send_notification.return_value.is_successful = True

            handle_push_notification(hamlet.id, missed_message)

            mock_fcm_messaging.send_each.assert_called_once()
            send_notification.assert_called_once()

            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sending push notifications to mobile clients for user {hamlet.id}",
                zerver_logger.output[0],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Skipping legacy push notifications for user {hamlet.id} because there are no registered devices",
                zerver_logger.output[1],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"APNs: Success sending to (push_account_id={registered_device_apple.push_account_id}, device={registered_device_apple.token})",
                zerver_logger.output[2],
            )
            self.assertEqual(
                "INFO:zilencer.lib.push_notifications:"
                f"FCM: Sent message with ID: 0 to (push_account_id={registered_device_android.push_account_id}, device={registered_device_android.token})",
                zilencer_logger.output[0],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sent E2EE mobile push notifications for user {hamlet.id}: 1 via FCM, 1 via APNs in 5.000s",
                zerver_logger.output[3],
            )

            realm_count_dict = (
                RealmCount.objects.filter(property="mobile_pushes_sent::day")
                .values("subgroup", "value")
                .last()
            )
            self.assertEqual(realm_count_dict, dict(subgroup=None, value=2))

    def test_no_registered_device(self) -> None:
        aaron = self.example_user("aaron")
        hamlet = self.example_user("hamlet")

        message_id = self.send_personal_message(
            from_user=aaron, to_user=hamlet, skip_capture_on_commit_callbacks=True
        )
        missed_message = {
            "message_id": message_id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }

        with self.assertLogs("zerver.lib.push_notifications", level="INFO") as zerver_logger:
            handle_push_notification(hamlet.id, missed_message)

            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sending push notifications to mobile clients for user {hamlet.id}",
                zerver_logger.output[0],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Skipping legacy push notifications for user {hamlet.id} because there are no registered devices",
                zerver_logger.output[1],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Skipping E2EE push notifications for user {hamlet.id} because there are no registered devices",
                zerver_logger.output[2],
            )

    def test_invalid_or_expired_token(self) -> None:
        aaron = self.example_user("aaron")
        hamlet = self.example_user("hamlet")

        registered_device_apple, registered_device_android = (
            self.register_push_devices_for_notification()
        )
        self.assertIsNone(registered_device_apple.expired_time)
        self.assertIsNone(registered_device_android.expired_time)
        self.assertEqual(PushDevice.objects.count(), 2)

        message_id = self.send_personal_message(
            from_user=aaron, to_user=hamlet, skip_capture_on_commit_callbacks=True
        )
        missed_message = {
            "message_id": message_id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }

        with (
            self.mock_fcm() as mock_fcm_messaging,
            self.mock_apns() as send_notification,
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as zerver_logger,
            self.assertLogs("zilencer.lib.push_notifications", level="INFO") as zilencer_logger,
            mock.patch("time.perf_counter", side_effect=[10.5, 11.0]),
        ):
            mock_fcm_messaging.send_each.return_value = self.make_fcm_error_response(
                UnregisteredError("Token expired")
            )
            send_notification.return_value.is_successful = False
            send_notification.return_value.description = "BadDeviceToken"

            handle_push_notification(hamlet.id, missed_message)

            mock_fcm_messaging.send_each.assert_called_once()
            send_notification.assert_called_once()

            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sending push notifications to mobile clients for user {hamlet.id}",
                zerver_logger.output[0],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"APNs: Removing invalid/expired token {registered_device_apple.token} (BadDeviceToken)",
                zerver_logger.output[2],
            )
            self.assertEqual(
                "INFO:zilencer.lib.push_notifications:"
                f"FCM: Removing {registered_device_android.token} due to NOT_FOUND",
                zilencer_logger.output[0],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Deleting PushDevice rows with the following device IDs based on response from bouncer: [{registered_device_apple.device_id}, {registered_device_android.device_id}]",
                zerver_logger.output[3],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sent E2EE mobile push notifications for user {hamlet.id}: 0 via FCM, 0 via APNs in 0.500s",
                zerver_logger.output[4],
            )

            # Verify `expired_time` set for `RemotePushDevice` entries
            # and corresponding `PushDevice` deleted on server.
            registered_device_apple.refresh_from_db()
            registered_device_android.refresh_from_db()
            self.assertIsNotNone(registered_device_apple.expired_time)
            self.assertIsNotNone(registered_device_android.expired_time)
            self.assertEqual(PushDevice.objects.count(), 0)

    def test_fcm_apns_error(self) -> None:
        hamlet = self.example_user("hamlet")
        aaron = self.example_user("aaron")

        _registered_device_apple, registered_device_android = (
            self.register_push_devices_for_notification()
        )
        message_id = self.send_personal_message(
            from_user=aaron, to_user=hamlet, skip_capture_on_commit_callbacks=True
        )
        missed_message = {
            "message_id": message_id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }

        # `get_apns_context` returns `None` + FCM returns error other than UnregisteredError.
        with (
            self.mock_fcm() as mock_fcm_messaging,
            mock.patch("zilencer.lib.push_notifications.get_apns_context", return_value=None),
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as zerver_logger,
            self.assertLogs("zilencer.lib.push_notifications", level="DEBUG") as zilencer_logger,
            mock.patch("time.perf_counter", side_effect=[10.0, 12.0]),
        ):
            mock_fcm_messaging.send_each.return_value = self.make_fcm_error_response(
                InternalError("fcm-error")
            )

            handle_push_notification(hamlet.id, missed_message)

            mock_fcm_messaging.send_each.assert_called_once()

            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sending push notifications to mobile clients for user {hamlet.id}",
                zerver_logger.output[0],
            )
            self.assertEqual(
                "DEBUG:zilencer.lib.push_notifications:"
                "APNs: Dropping a notification because nothing configured. "
                "Set ZULIP_SERVICES_URL (or APNS_CERT_FILE).",
                zilencer_logger.output[0],
            )
            self.assertIn(
                "WARNING:zilencer.lib.push_notifications:"
                f"FCM: Delivery failed for (push_account_id={registered_device_android.push_account_id}, device={registered_device_android.token})",
                zilencer_logger.output[1],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sent E2EE mobile push notifications for user {hamlet.id}: 0 via FCM, 0 via APNs in 2.000s",
                zerver_logger.output[2],
            )

        # `firebase_messaging.send_each` raises Error.
        message_id = self.send_personal_message(
            from_user=aaron, to_user=hamlet, skip_capture_on_commit_callbacks=True
        )
        missed_message = {
            "message_id": message_id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }

        with (
            self.mock_fcm() as mock_fcm_messaging,
            mock.patch(
                "zilencer.lib.push_notifications.send_e2ee_push_notification_apple",
                return_value=SentPushNotificationResult(
                    successfully_sent_count=1,
                    delete_device_ids=[],
                ),
            ),
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as zerver_logger,
            self.assertLogs("zilencer.lib.push_notifications", level="WARNING") as zilencer_logger,
            mock.patch("time.perf_counter", side_effect=[10.0, 12.0]),
        ):
            mock_fcm_messaging.send_each.side_effect = InternalError("server error")
            handle_push_notification(hamlet.id, missed_message)

            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sending push notifications to mobile clients for user {hamlet.id}",
                zerver_logger.output[0],
            )
            self.assertIn(
                "WARNING:zilencer.lib.push_notifications:Error while pushing to FCM",
                zilencer_logger.output[0],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sent E2EE mobile push notifications for user {hamlet.id}: 0 via FCM, 1 via APNs in 2.000s",
                zerver_logger.output[2],
            )

    def test_early_return_if_expired_time_set(self) -> None:
        aaron = self.example_user("aaron")
        hamlet = self.example_user("hamlet")

        registered_device_apple, registered_device_android = (
            self.register_push_devices_for_notification()
        )
        registered_device_apple.expired_time = datetime(2099, 4, 24, tzinfo=timezone.utc)
        registered_device_android.expired_time = datetime(2099, 4, 24, tzinfo=timezone.utc)
        registered_device_apple.save(update_fields=["expired_time"])
        registered_device_android.save(update_fields=["expired_time"])

        self.assertEqual(PushDevice.objects.count(), 2)

        message_id = self.send_personal_message(
            from_user=aaron, to_user=hamlet, skip_capture_on_commit_callbacks=True
        )
        missed_message = {
            "message_id": message_id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }

        # Since 'expired_time' is set for concerned 'RemotePushDevice' rows,
        # the bouncer will not attempt to send notification and instead returns
        # a list of device IDs which server should erase on their own end.
        with (
            mock.patch(
                "zilencer.lib.push_notifications.send_e2ee_push_notification_apple"
            ) as send_apple,
            mock.patch(
                "zilencer.lib.push_notifications.send_e2ee_push_notification_android"
            ) as send_android,
        ):
            handle_push_notification(hamlet.id, missed_message)

            send_apple.assert_not_called()
            send_android.assert_not_called()
            self.assertEqual(PushDevice.objects.count(), 0)

    @responses.activate
    @override_settings(ZILENCER_ENABLED=False)
    def test_success_self_hosted(self) -> None:
        self.add_mock_response()

        hamlet = self.example_user("hamlet")
        aaron = self.example_user("aaron")
        realm = hamlet.realm

        registered_device_apple, registered_device_android = (
            self.register_push_devices_for_notification(is_server_self_hosted=True)
        )
        message_id = self.send_personal_message(
            from_user=aaron, to_user=hamlet, skip_capture_on_commit_callbacks=True
        )
        missed_message = {
            "message_id": message_id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }

        # Setup to verify whether these fields get updated correctly.
        realm.push_notifications_enabled = False
        realm.push_notifications_enabled_end_timestamp = datetime(2099, 4, 24, tzinfo=timezone.utc)
        realm.save(
            update_fields=["push_notifications_enabled", "push_notifications_enabled_end_timestamp"]
        )

        self.assertEqual(RealmCount.objects.count(), 0)
        self.assertEqual(RemoteRealmCount.objects.count(), 0)

        with (
            self.mock_fcm() as mock_fcm_messaging,
            self.mock_apns() as send_notification,
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
                return_value=10,
            ),
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as zerver_logger,
            self.assertLogs("zilencer.lib.push_notifications", level="INFO") as zilencer_logger,
            mock.patch("time.perf_counter", side_effect=[10.05, 12.10]),
        ):
            mock_fcm_messaging.send_each.return_value = self.make_fcm_success_response()
            send_notification.return_value.is_successful = True

            handle_push_notification(hamlet.id, missed_message)

            mock_fcm_messaging.send_each.assert_called_once()
            send_notification.assert_called_once()

            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sending push notifications to mobile clients for user {hamlet.id}",
                zerver_logger.output[0],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Skipping legacy push notifications for user {hamlet.id} because there are no registered devices",
                zerver_logger.output[1],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"APNs: Success sending to (push_account_id={registered_device_apple.push_account_id}, device={registered_device_apple.token})",
                zerver_logger.output[2],
            )
            self.assertEqual(
                "INFO:zilencer.lib.push_notifications:"
                f"FCM: Sent message with ID: 0 to (push_account_id={registered_device_android.push_account_id}, device={registered_device_android.token})",
                zilencer_logger.output[0],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sent E2EE mobile push notifications for user {hamlet.id}: 1 via FCM, 1 via APNs in 2.050s",
                zerver_logger.output[3],
            )

            realm_count_dict = (
                RealmCount.objects.filter(property="mobile_pushes_sent::day")
                .values("subgroup", "value")
                .last()
            )
            self.assertEqual(realm_count_dict, dict(subgroup=None, value=2))

            remote_realm_count_dict = (
                RemoteRealmCount.objects.filter(property="mobile_pushes_received::day")
                .values("subgroup", "value")
                .last()
            )
            self.assertEqual(remote_realm_count_dict, dict(subgroup=None, value=2))

            remote_realm_count_dict = (
                RemoteRealmCount.objects.filter(property="mobile_pushes_forwarded::day")
                .values("subgroup", "value")
                .last()
            )
            self.assertEqual(remote_realm_count_dict, dict(subgroup=None, value=2))

            realm.refresh_from_db()
            self.assertTrue(realm.push_notifications_enabled)
            self.assertIsNone(realm.push_notifications_enabled_end_timestamp)

    @responses.activate
    @override_settings(ZILENCER_ENABLED=False)
    def test_missing_remote_realm_error(self) -> None:
        self.add_mock_response()

        hamlet = self.example_user("hamlet")
        aaron = self.example_user("aaron")
        realm = hamlet.realm

        self.register_push_devices_for_notification(is_server_self_hosted=True)
        message_id = self.send_personal_message(
            from_user=aaron, to_user=hamlet, skip_capture_on_commit_callbacks=True
        )
        missed_message = {
            "message_id": message_id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }

        # Setup to verify whether these fields get updated correctly.
        realm.push_notifications_enabled = True
        realm.push_notifications_enabled_end_timestamp = datetime(2099, 4, 24, tzinfo=timezone.utc)
        realm.save(
            update_fields=["push_notifications_enabled", "push_notifications_enabled_end_timestamp"]
        )

        # To replicate missing remote realm
        RemoteRealm.objects.all().delete()

        with (
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as zerver_logger,
            self.assertLogs("zilencer.views", level="INFO") as zilencer_logger,
        ):
            handle_push_notification(hamlet.id, missed_message)

            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sending push notifications to mobile clients for user {hamlet.id}",
                zerver_logger.output[0],
            )
            self.assertEqual(
                "INFO:zilencer.views:"
                f"/api/v1/remotes/push/e2ee/notify: Received request for unknown realm {realm.uuid}, server {self.server.id}",
                zilencer_logger.output[0],
            )
            self.assertEqual(
                "WARNING:zerver.lib.push_notifications:"
                "Bouncer refused to send E2EE push notification: Organization not registered",
                zerver_logger.output[2],
            )

            realm.refresh_from_db()
            self.assertFalse(realm.push_notifications_enabled)
            self.assertIsNone(realm.push_notifications_enabled_end_timestamp)

    @responses.activate
    @override_settings(ZILENCER_ENABLED=False)
    def test_no_plan_error(self) -> None:
        self.add_mock_response()

        hamlet = self.example_user("hamlet")
        aaron = self.example_user("aaron")
        realm = hamlet.realm

        self.register_push_devices_for_notification(is_server_self_hosted=True)
        message_id = self.send_personal_message(
            from_user=aaron, to_user=hamlet, skip_capture_on_commit_callbacks=True
        )
        missed_message = {
            "message_id": message_id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }

        # Setup to verify whether these fields get updated correctly.
        realm.push_notifications_enabled = True
        realm.push_notifications_enabled_end_timestamp = datetime(2099, 4, 24, tzinfo=timezone.utc)
        realm.save(
            update_fields=["push_notifications_enabled", "push_notifications_enabled_end_timestamp"]
        )

        with (
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
                return_value=100,
            ),
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as zerver_logger,
        ):
            handle_push_notification(hamlet.id, missed_message)

            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sending push notifications to mobile clients for user {hamlet.id}",
                zerver_logger.output[0],
            )
            self.assertEqual(
                "WARNING:zerver.lib.push_notifications:"
                "Bouncer refused to send E2EE push notification: Your plan doesn't allow sending push notifications. "
                "Reason provided by the server: Push notifications access with 10+ users requires signing up for a plan. https://zulip.com/plans/",
                zerver_logger.output[2],
            )

            realm.refresh_from_db()
            self.assertFalse(realm.push_notifications_enabled)
            self.assertIsNone(realm.push_notifications_enabled_end_timestamp)

    def test_both_old_and_new_client_coexists(self) -> None:
        """Test coexistence of old (which don't support E2EE)
        and new client devices registered for push notifications.
        """
        hamlet = self.example_user("hamlet")
        aaron = self.example_user("aaron")

        registered_device_apple, registered_device_android = (
            self.register_push_devices_for_notification()
        )
        registered_device_apple_old, registered_device_android_old = (
            self.register_old_push_devices_for_notification()
        )

        message_id = self.send_personal_message(
            from_user=aaron, to_user=hamlet, skip_capture_on_commit_callbacks=True
        )
        missed_message = {
            "message_id": message_id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }

        self.assertEqual(RealmCount.objects.count(), 0)

        with (
            self.mock_fcm(for_legacy=True) as mock_fcm_messaging_legacy,
            self.mock_apns(for_legacy=True) as send_notification_legacy,
            self.mock_fcm() as mock_fcm_messaging,
            self.mock_apns() as send_notification,
            mock.patch(
                "zerver.lib.push_notifications.uses_notification_bouncer", return_value=False
            ),
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as zerver_logger,
            self.assertLogs("zilencer.lib.push_notifications", level="INFO") as zilencer_logger,
            mock.patch("time.perf_counter", side_effect=[10.0, 12.0]),
        ):
            mock_fcm_messaging_legacy.send_each.return_value = self.make_fcm_success_response(
                for_legacy=True
            )
            send_notification_legacy.return_value.is_successful = True
            mock_fcm_messaging.send_each.return_value = self.make_fcm_success_response()
            send_notification.return_value.is_successful = True

            handle_push_notification(hamlet.id, missed_message)

            mock_fcm_messaging_legacy.send_each.assert_called_once()
            send_notification_legacy.assert_called_once()
            mock_fcm_messaging.send_each.assert_called_once()
            send_notification.assert_called_once()

            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sending push notifications to mobile clients for user {hamlet.id}",
                zerver_logger.output[0],
            )
            # Logs in legacy codepath
            self.assertEqual(
                zerver_logger.output[1:6],
                [
                    f"INFO:zerver.lib.push_notifications:Sending mobile push notifications for local user {hamlet.id}: 1 via FCM devices, 1 via APNs devices",
                    f"INFO:zerver.lib.push_notifications:APNs: Sending notification for local user <id:{hamlet.id}> to 1 devices (skipped 0 duplicates)",
                    f"INFO:zerver.lib.push_notifications:APNs: Success sending for user <id:{hamlet.id}> to device {registered_device_apple_old.token}",
                    f"INFO:zerver.lib.push_notifications:FCM: Sending notification for local user <id:{hamlet.id}> to 1 devices",
                    f"INFO:zerver.lib.push_notifications:FCM: Sent message with ID: 0 to {registered_device_android_old.token}",
                ],
            )
            # Logs in E2EE codepath
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"APNs: Success sending to (push_account_id={registered_device_apple.push_account_id}, device={registered_device_apple.token})",
                zerver_logger.output[6],
            )
            self.assertEqual(
                "INFO:zilencer.lib.push_notifications:"
                f"FCM: Sent message with ID: 0 to (push_account_id={registered_device_android.push_account_id}, device={registered_device_android.token})",
                zilencer_logger.output[0],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sent E2EE mobile push notifications for user {hamlet.id}: 1 via FCM, 1 via APNs in 2.000s",
                zerver_logger.output[7],
            )

            realm_count_dict = (
                RealmCount.objects.filter(property="mobile_pushes_sent::day")
                .values("subgroup", "value")
                .last()
            )
            self.assertEqual(realm_count_dict, dict(subgroup=None, value=4))

    def test_payload_data_to_encrypt_channel_message(self) -> None:
        hamlet = self.example_user("hamlet")
        aaron = self.example_user("aaron")
        realm = get_realm("zulip")
        user_group = check_add_user_group(realm, "test_user_group", [hamlet], acting_user=hamlet)

        time_now = now()
        self.subscribe(aaron, "Denmark")
        with time_machine.travel(time_now, tick=False):
            message_id = self.send_stream_message(
                sender=aaron,
                stream_name="Denmark",
                content=f"@*{user_group.name}*",
                skip_capture_on_commit_callbacks=True,
            )
        missed_message = {
            "message_id": message_id,
            "trigger": NotificationTriggers.MENTION,
            "mentioned_user_group_id": user_group.id,
        }

        expected_payload_data_to_encrypt = {
            "realm_url": realm.url,
            "realm_name": realm.name,
            "user_id": hamlet.id,
            "sender_id": aaron.id,
            "mentioned_user_group_id": user_group.id,
            "mentioned_user_group_name": user_group.name,
            "recipient_type": "channel",
            "channel_name": "Denmark",
            "channel_id": self.get_stream_id("Denmark"),
            "topic": "test",
            "type": "message",
            "message_id": message_id,
            "time": datetime_to_timestamp(time_now),
            "content": f"@{user_group.name}",
            "sender_full_name": aaron.full_name,
            "sender_avatar_url": absolute_avatar_url(aaron),
        }
        with mock.patch("zerver.lib.push_notifications.send_push_notifications") as m:
            handle_push_notification(hamlet.id, missed_message)

            self.assertEqual(m.call_args.args[1], expected_payload_data_to_encrypt)

    def test_payload_data_to_encrypt_direct_message(self) -> None:
        hamlet = self.example_user("hamlet")
        aaron = self.example_user("aaron")
        realm = get_realm("zulip")

        time_now = now()
        with time_machine.travel(time_now, tick=False):
            message_id = self.send_personal_message(
                from_user=aaron, to_user=hamlet, skip_capture_on_commit_callbacks=True
            )
        missed_message = {
            "message_id": message_id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }

        expected_payload_data_to_encrypt = {
            "realm_url": realm.url,
            "realm_name": realm.name,
            "user_id": hamlet.id,
            "sender_id": aaron.id,
            "recipient_type": "direct",
            "type": "message",
            "message_id": message_id,
            "time": datetime_to_timestamp(time_now),
            "content": "test content",
            "sender_full_name": aaron.full_name,
            "sender_avatar_url": absolute_avatar_url(aaron),
        }
        with mock.patch("zerver.lib.push_notifications.send_push_notifications") as m:
            handle_push_notification(hamlet.id, missed_message)

            self.assertEqual(m.call_args.args[1], expected_payload_data_to_encrypt)


@activate_push_notification_service()
class RemovePushNotificationTest(E2EEPushNotificationTestCase):
    def test_success_cloud(self) -> None:
        hamlet = self.example_user("hamlet")
        aaron = self.example_user("aaron")

        self.register_push_devices_for_notification()
        message_id = self.send_personal_message(
            from_user=aaron, to_user=hamlet, skip_capture_on_commit_callbacks=True
        )
        user_message = UserMessage.objects.get(user_profile=hamlet, message_id=message_id)
        user_message.flags.active_mobile_push_notification = True
        user_message.save(update_fields=["flags"])

        with (
            self.mock_fcm() as mock_fcm_messaging,
            self.mock_apns() as send_notification,
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as zerver_logger,
            self.assertLogs("zilencer.lib.push_notifications", level="INFO"),
            mock.patch("time.perf_counter", side_effect=[10.0, 12.0]),
        ):
            mock_fcm_messaging.send_each.return_value = self.make_fcm_success_response()
            send_notification.return_value.is_successful = True

            handle_remove_push_notification(hamlet.id, [message_id])

            mock_fcm_messaging.send_each.assert_called_once()
            send_notification.assert_called_once()

            user_message.refresh_from_db()
            self.assertFalse(user_message.flags.active_mobile_push_notification)

            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sent E2EE mobile push notifications for user {hamlet.id}: 1 via FCM, 1 via APNs in 2.000s",
                zerver_logger.output[2],
            )

    @responses.activate
    @override_settings(ZILENCER_ENABLED=False)
    def test_success_self_hosted(self) -> None:
        self.add_mock_response()

        hamlet = self.example_user("hamlet")
        aaron = self.example_user("aaron")

        self.register_push_devices_for_notification(is_server_self_hosted=True)
        message_id = self.send_personal_message(
            from_user=aaron, to_user=hamlet, skip_capture_on_commit_callbacks=True
        )
        user_message = UserMessage.objects.get(user_profile=hamlet, message_id=message_id)
        user_message.flags.active_mobile_push_notification = True
        user_message.save(update_fields=["flags"])

        with (
            self.mock_fcm() as mock_fcm_messaging,
            self.mock_apns() as send_notification,
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
                return_value=10,
            ),
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as zerver_logger,
            self.assertLogs("zilencer.lib.push_notifications", level="INFO"),
            mock.patch("time.perf_counter", side_effect=[10.0, 12.0]),
        ):
            mock_fcm_messaging.send_each.return_value = self.make_fcm_success_response()
            send_notification.return_value.is_successful = True

            handle_remove_push_notification(hamlet.id, [message_id])

            mock_fcm_messaging.send_each.assert_called_once()
            send_notification.assert_called_once()

            user_message.refresh_from_db()
            self.assertFalse(user_message.flags.active_mobile_push_notification)

            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sent E2EE mobile push notifications for user {hamlet.id}: 1 via FCM, 1 via APNs in 2.000s",
                zerver_logger.output[2],
            )

    def test_remove_payload_data_to_encrypt(self) -> None:
        hamlet = self.example_user("hamlet")
        aaron = self.example_user("aaron")
        realm = get_realm("zulip")

        message_id_one = self.send_personal_message(
            from_user=aaron, to_user=hamlet, skip_capture_on_commit_callbacks=True
        )
        message_id_two = self.send_personal_message(
            from_user=aaron, to_user=hamlet, skip_capture_on_commit_callbacks=True
        )

        expected_payload_data_to_encrypt = {
            "realm_url": realm.url,
            "realm_name": realm.name,
            "user_id": hamlet.id,
            "type": "remove",
            "message_ids": [message_id_one, message_id_two],
        }
        with mock.patch("zerver.lib.push_notifications.send_push_notifications") as m:
            handle_remove_push_notification(hamlet.id, [message_id_one, message_id_two])

            self.assertEqual(m.call_args.args[1], expected_payload_data_to_encrypt)


class RequireE2EEPushNotificationsSettingTest(E2EEPushNotificationTestCase):
    def test_content_redacted(self) -> None:
        hamlet = self.example_user("hamlet")
        aaron = self.example_user("aaron")
        realm = hamlet.realm

        self.register_old_push_devices_for_notification()
        self.register_push_devices_for_notification()

        message_id = self.send_personal_message(
            from_user=aaron,
            to_user=hamlet,
            content="not-redacted",
            skip_capture_on_commit_callbacks=True,
        )
        missed_message = {
            "message_id": message_id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }

        realm.require_e2ee_push_notifications = True
        realm.save(update_fields=["require_e2ee_push_notifications"])

        # Verify that the content is redacted in payloads supplied to
        # 'send_notifications_to_bouncer' - payloads supplied to bouncer (legacy codepath).
        #
        # Verify that the content is not redacted in payloads supplied to
        # 'send_push_notifications' - payloads which get encrypted.
        with (
            activate_push_notification_service(),
            mock.patch(
                "zerver.lib.push_notifications.send_notifications_to_bouncer"
            ) as mock_legacy,
            mock.patch("zerver.lib.push_notifications.send_push_notifications") as mock_e2ee,
        ):
            handle_push_notification(hamlet.id, missed_message)

            mock_legacy.assert_called_once()
            self.assertEqual(mock_legacy.call_args.args[1]["alert"]["body"], "New message")
            self.assertEqual(mock_legacy.call_args.args[2]["content"], "New message")

            mock_e2ee.assert_called_once()
            self.assertEqual(mock_e2ee.call_args.args[1]["content"], "not-redacted")

        message_id = self.send_personal_message(
            from_user=aaron, to_user=hamlet, skip_capture_on_commit_callbacks=True
        )
        missed_message = {
            "message_id": message_id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }

        # Verify that the content is redacted in payloads supplied to
        # to functions for sending it through APNs and FCM directly.
        with (
            mock.patch("zerver.lib.push_notifications.has_apns_credentials", return_value=True),
            mock.patch("zerver.lib.push_notifications.has_fcm_credentials", return_value=True),
            mock.patch(
                "zerver.lib.push_notifications.send_notifications_to_bouncer"
            ) as send_bouncer,
            mock.patch(
                "zerver.lib.push_notifications.send_apple_push_notification", return_value=0
            ) as send_apple,
            mock.patch(
                "zerver.lib.push_notifications.send_android_push_notification", return_value=0
            ) as send_android,
            # We have already asserted the payloads passed to E2EE codepath above.
            mock.patch("zerver.lib.push_notifications.send_push_notifications"),
        ):
            handle_push_notification(hamlet.id, missed_message)

            send_bouncer.assert_not_called()
            send_apple.assert_called_once()
            send_android.assert_called_once()

            self.assertEqual(send_apple.call_args.args[2]["alert"]["body"], "New message")
            self.assertEqual(send_android.call_args.args[2]["content"], "New message")


class SendTestPushNotificationTest(E2EEPushNotificationTestCase):
    def test_success_cloud(self) -> None:
        hamlet = self.example_user("hamlet")
        _registered_device_apple, registered_device_android = (
            self.register_push_devices_for_notification()
        )

        with (
            self.mock_fcm() as mock_fcm_messaging,
            self.mock_apns() as send_notification,
            self.assertLogs("zilencer.lib.push_notifications", level="INFO"),
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as zerver_logger,
            mock.patch("time.perf_counter", side_effect=[10.0, 12.0, 13.0, 16.0]),
        ):
            mock_fcm_messaging.send_each.return_value = self.make_fcm_success_response()
            send_notification.return_value.is_successful = True

            # Send test notification to all of the registered mobile devices.
            result = self.api_post(
                hamlet, "/api/v1/mobile_push/e2ee/test_notification", subdomain="zulip"
            )
            self.assert_json_success(result)

            mock_fcm_messaging.send_each.assert_called_once()
            send_notification.assert_called_once()

            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sending E2EE test push notification for user {hamlet.id}",
                zerver_logger.output[0],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sent E2EE mobile push notifications for user {hamlet.id}: 1 via FCM, 1 via APNs in 2.000s",
                zerver_logger.output[-1],
            )

            # Send test notification to a selected mobile device.
            result = self.api_post(
                hamlet,
                "/api/v1/mobile_push/e2ee/test_notification",
                {"push_account_id": registered_device_android.push_account_id},
                subdomain="zulip",
            )
            self.assert_json_success(result)

            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sending E2EE test push notification for user {hamlet.id}",
                zerver_logger.output[0],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sent E2EE mobile push notifications for user {hamlet.id}: 1 via FCM, 0 via APNs in 3.000s",
                zerver_logger.output[-1],
            )

    @responses.activate
    @override_settings(ZILENCER_ENABLED=False)
    def test_success_self_hosted(self) -> None:
        self.add_mock_response()

        hamlet = self.example_user("hamlet")
        self.register_push_devices_for_notification(is_server_self_hosted=True)

        with (
            self.mock_fcm() as mock_fcm_messaging,
            self.mock_apns() as send_notification,
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
                return_value=10,
            ),
            self.assertLogs("zilencer.lib.push_notifications", level="INFO"),
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as zerver_logger,
            mock.patch("time.perf_counter", side_effect=[10.0, 12.0]),
        ):
            mock_fcm_messaging.send_each.return_value = self.make_fcm_success_response()
            send_notification.return_value.is_successful = True

            # Send test notification to all of the registered mobile devices.
            result = self.api_post(
                hamlet, "/api/v1/mobile_push/e2ee/test_notification", subdomain="zulip"
            )
            self.assert_json_success(result)

            mock_fcm_messaging.send_each.assert_called_once()
            send_notification.assert_called_once()

            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sending E2EE test push notification for user {hamlet.id}",
                zerver_logger.output[0],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sent E2EE mobile push notifications for user {hamlet.id}: 1 via FCM, 1 via APNs in 2.000s",
                zerver_logger.output[-1],
            )

    @responses.activate
    @override_settings(ZILENCER_ENABLED=False)
    def test_error_responses(self) -> None:
        self.add_mock_response()
        hamlet = self.example_user("hamlet")

        # No registered device to send to.
        result = self.api_post(
            hamlet, "/api/v1/mobile_push/e2ee/test_notification", subdomain="zulip"
        )
        self.assert_json_error(result, "No active registered push device", 400)

        # Verify errors propagated to the client.
        registered_device_apple, registered_device_android = (
            self.register_push_devices_for_notification(is_server_self_hosted=True)
        )

        def assert_error_response(msg: str, http_status_code: int) -> None:
            with self.assertLogs("zerver.lib.push_notifications", level="INFO") as zerver_logger:
                result = self.api_post(
                    hamlet, "/api/v1/mobile_push/e2ee/test_notification", subdomain="zulip"
                )
                self.assert_json_error(result, msg, http_status_code)

                self.assertEqual(
                    "INFO:zerver.lib.push_notifications:"
                    f"Sending E2EE test push notification for user {hamlet.id}",
                    zerver_logger.output[0],
                )

        with (
            mock.patch(
                "zerver.lib.remote_server.send_to_push_bouncer",
                side_effect=PushNotificationBouncerRetryLaterError("network error"),
            ),
            self.assertLogs(level="ERROR") as error_logs,
        ):
            assert_error_response(
                "Network error while connecting to Zulip push notification service.", 502
            )
            self.assertEqual(
                "ERROR:django.request:Bad Gateway: /api/v1/mobile_push/e2ee/test_notification",
                error_logs.output[0],
            )

        with (
            mock.patch(
                "zerver.lib.remote_server.send_to_push_bouncer",
                side_effect=PushNotificationBouncerServerError("server error"),
            ),
            self.assertLogs(level="ERROR") as error_logs,
        ):
            assert_error_response(
                "Internal server error on Zulip push notification service, retry later.", 502
            )
            self.assertEqual(
                "ERROR:django.request:Bad Gateway: /api/v1/mobile_push/e2ee/test_notification",
                error_logs.output[0],
            )

        with mock.patch(
            "zerver.lib.remote_server.send_to_push_bouncer", side_effect=MissingRemoteRealmError
        ):
            assert_error_response(
                "Push notification configuration issue on server, contact the server administrator or retry later.",
                403,
            )

        with mock.patch(
            "zerver.lib.remote_server.send_to_push_bouncer",
            side_effect=PushNotificationBouncerError,
        ):
            assert_error_response(
                "Push notification configuration issue on server, contact the server administrator or retry later.",
                403,
            )

        with mock.patch(
            "zerver.lib.remote_server.send_to_push_bouncer",
            side_effect=PushNotificationsDisallowedByBouncerError("plan expired"),
        ):
            assert_error_response(
                "Push notification configuration issue on server, contact the server administrator or retry later.",
                403,
            )

        # Device marked expired on bouncer (not on server).
        registered_device_apple.delete()
        registered_device_android.delete()

        with mock.patch(
            "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
            return_value=10,
        ):
            assert_error_response("No active registered push device", 400)
