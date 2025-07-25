from datetime import datetime, timezone
from unittest import mock

import responses
from django.test import override_settings
from firebase_admin.exceptions import InternalError
from firebase_admin.messaging import UnregisteredError

from analytics.models import RealmCount
from zerver.lib.push_notifications import handle_push_notification, handle_remove_push_notification
from zerver.lib.test_classes import E2EEPushNotificationTestCase
from zerver.lib.test_helpers import activate_push_notification_service
from zerver.models import PushDevice, UserMessage
from zerver.models.scheduled_jobs import NotificationTriggers
from zilencer.models import RemoteRealm, RemoteRealmCount


@activate_push_notification_service()
@mock.patch("zerver.lib.push_notifications.send_push_notifications_legacy")
class SendPushNotificationTest(E2EEPushNotificationTestCase):
    def test_success_cloud(self, unused_mock: mock.MagicMock) -> None:
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
                f"APNs: Success sending to (push_account_id={registered_device_apple.push_account_id}, device={registered_device_apple.token})",
                zerver_logger.output[1],
            )
            self.assertEqual(
                "INFO:zilencer.lib.push_notifications:"
                f"FCM: Sent message with ID: 0 to (push_account_id={registered_device_android.push_account_id}, device={registered_device_android.token})",
                zilencer_logger.output[0],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sent E2EE mobile push notifications for user {hamlet.id}: 1 via FCM, 1 via APNs",
                zerver_logger.output[2],
            )

            realm_count_dict = (
                RealmCount.objects.filter(property="mobile_pushes_sent::day")
                .values("subgroup", "value")
                .last()
            )
            self.assertEqual(realm_count_dict, dict(subgroup=None, value=2))

    def test_no_registered_device(self, unused_mock: mock.MagicMock) -> None:
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
                f"Skipping E2EE push notifications for user {hamlet.id} because there are no registered devices",
                zerver_logger.output[1],
            )

    def test_invalid_or_expired_token(self, unused_mock: mock.MagicMock) -> None:
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
                zerver_logger.output[1],
            )
            self.assertEqual(
                "INFO:zilencer.lib.push_notifications:"
                f"FCM: Removing {registered_device_android.token} due to NOT_FOUND",
                zilencer_logger.output[0],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Deleting PushDevice rows with the following device IDs based on response from bouncer: [{registered_device_apple.device_id}, {registered_device_android.device_id}]",
                zerver_logger.output[2],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sent E2EE mobile push notifications for user {hamlet.id}: 0 via FCM, 0 via APNs",
                zerver_logger.output[3],
            )

            # Verify `expired_time` set for `RemotePushDevice` entries
            # and corresponding `PushDevice` deleted on server.
            registered_device_apple.refresh_from_db()
            registered_device_android.refresh_from_db()
            self.assertIsNotNone(registered_device_apple.expired_time)
            self.assertIsNotNone(registered_device_android.expired_time)
            self.assertEqual(PushDevice.objects.count(), 0)

    def test_fcm_apns_error(self, unused_mock: mock.MagicMock) -> None:
        hamlet = self.example_user("hamlet")
        aaron = self.example_user("aaron")

        unused, registered_device_android = self.register_push_devices_for_notification()
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
                f"Sent E2EE mobile push notifications for user {hamlet.id}: 0 via FCM, 0 via APNs",
                zerver_logger.output[1],
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
                "zilencer.lib.push_notifications.send_e2ee_push_notification_apple", return_value=1
            ),
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as zerver_logger,
            self.assertLogs("zilencer.lib.push_notifications", level="WARNING") as zilencer_logger,
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
                f"Sent E2EE mobile push notifications for user {hamlet.id}: 0 via FCM, 1 via APNs",
                zerver_logger.output[1],
            )

    def test_early_return_if_expired_time_set(self, unused_mock: mock.MagicMock) -> None:
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
    def test_success_self_hosted(self, unused_mock: mock.MagicMock) -> None:
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
                f"APNs: Success sending to (push_account_id={registered_device_apple.push_account_id}, device={registered_device_apple.token})",
                zerver_logger.output[1],
            )
            self.assertEqual(
                "INFO:zilencer.lib.push_notifications:"
                f"FCM: Sent message with ID: 0 to (push_account_id={registered_device_android.push_account_id}, device={registered_device_android.token})",
                zilencer_logger.output[0],
            )
            self.assertEqual(
                "INFO:zerver.lib.push_notifications:"
                f"Sent E2EE mobile push notifications for user {hamlet.id}: 1 via FCM, 1 via APNs",
                zerver_logger.output[2],
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
    def test_missing_remote_realm_error(self, unused_mock: mock.MagicMock) -> None:
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
                zerver_logger.output[1],
            )

            realm.refresh_from_db()
            self.assertFalse(realm.push_notifications_enabled)
            self.assertIsNone(realm.push_notifications_enabled_end_timestamp)

    @responses.activate
    @override_settings(ZILENCER_ENABLED=False)
    def test_no_plan_error(self, unused_mock: mock.MagicMock) -> None:
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
                zerver_logger.output[1],
            )

            realm.refresh_from_db()
            self.assertFalse(realm.push_notifications_enabled)
            self.assertIsNone(realm.push_notifications_enabled_end_timestamp)


@activate_push_notification_service()
@mock.patch("zerver.lib.push_notifications.send_push_notifications_legacy")
class RemovePushNotificationTest(E2EEPushNotificationTestCase):
    def test_success_cloud(self, unused_mock: mock.MagicMock) -> None:
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
                f"Sent E2EE mobile push notifications for user {hamlet.id}: 1 via FCM, 1 via APNs",
                zerver_logger.output[1],
            )

    @responses.activate
    @override_settings(ZILENCER_ENABLED=False)
    def test_success_self_hosted(self, unused_mock: mock.MagicMock) -> None:
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
                f"Sent E2EE mobile push notifications for user {hamlet.id}: 1 via FCM, 1 via APNs",
                zerver_logger.output[1],
            )
