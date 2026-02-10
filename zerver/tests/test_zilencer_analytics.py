import logging
import uuid
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest import mock

import orjson
import responses
import time_machine
from django.conf import settings
from django.db.models import F
from django.utils.timezone import now
from requests.exceptions import ConnectionError
from typing_extensions import override

from analytics.lib.counts import CountStat, LoggingCountStat
from analytics.models import InstallationCount, RealmCount, UserCount
from corporate.lib.stripe import RemoteRealmBillingSession
from corporate.models.plans import CustomerPlan
from version import ZULIP_VERSION
from zerver.actions.create_realm import do_create_realm
from zerver.actions.realm_settings import (
    do_change_realm_org_type,
    do_deactivate_realm,
    do_set_realm_authentication_methods,
)
from zerver.lib import redis_utils
from zerver.lib.remote_server import (
    PUSH_NOTIFICATIONS_RECENTLY_WORKING_REDIS_KEY,
    AnalyticsRequest,
    PushNotificationBouncerRetryLaterError,
    build_analytics_data,
    get_realms_info_for_push_bouncer,
    record_push_notifications_recently_working,
    redis_client,
    send_server_data_to_push_bouncer,
    send_to_push_bouncer,
)
from zerver.lib.test_classes import BouncerTestCase
from zerver.lib.test_helpers import activate_push_notification_service
from zerver.lib.types import AnalyticsDataUploadLevel
from zerver.lib.user_counts import realm_user_count_by_role
from zerver.models import Realm, RealmAuditLog
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.realms import get_realm
from zilencer.lib.remote_counts import MissingDataError

if settings.ZILENCER_ENABLED:
    from zilencer.models import (
        RemoteInstallationCount,
        RemoteRealm,
        RemoteRealmAuditLog,
        RemoteRealmCount,
        RemoteZulipServer,
    )


class AnalyticsBouncerTest(BouncerTestCase):
    TIME_ZERO = datetime(1988, 3, 14, tzinfo=timezone.utc)

    def assertPushNotificationsAre(self, should_be: bool) -> None:
        self.assertEqual(
            {should_be},
            set(
                Realm.objects.all().distinct().values_list("push_notifications_enabled", flat=True)
            ),
        )

    @override
    def setUp(self) -> None:
        redis_client.delete(PUSH_NOTIFICATIONS_RECENTLY_WORKING_REDIS_KEY)

        return super().setUp()

    @activate_push_notification_service()
    @responses.activate
    def test_analytics_failure_api(self) -> None:
        assert settings.ZULIP_SERVICES_URL is not None
        ANALYTICS_URL = settings.ZULIP_SERVICES_URL + "/api/v1/remotes/server/analytics"
        ANALYTICS_STATUS_URL = ANALYTICS_URL + "/status"

        with (
            responses.RequestsMock() as resp,
            self.assertLogs("zulip.analytics", level="WARNING") as mock_warning,
        ):
            resp.add(responses.GET, ANALYTICS_STATUS_URL, body=ConnectionError())
            Realm.objects.all().update(push_notifications_enabled=True)
            send_server_data_to_push_bouncer()
            self.assertEqual(
                "WARNING:zulip.analytics:ConnectionError while trying to connect to push notification bouncer",
                mock_warning.output[0],
            )
            self.assertTrue(resp.assert_call_count(ANALYTICS_STATUS_URL, 1))
            self.assertPushNotificationsAre(False)

        # Simulate ConnectionError again, but this time with a redis record indicating
        # that push notifications have recently worked fine.
        with (
            responses.RequestsMock() as resp,
            self.assertLogs("zulip.analytics", level="WARNING") as mock_warning,
        ):
            resp.add(responses.GET, ANALYTICS_STATUS_URL, body=ConnectionError())
            Realm.objects.all().update(push_notifications_enabled=True)
            record_push_notifications_recently_working()

            send_server_data_to_push_bouncer()
            self.assertEqual(
                "WARNING:zulip.analytics:ConnectionError while trying to connect to push notification bouncer",
                mock_warning.output[0],
            )
            self.assertTrue(resp.assert_call_count(ANALYTICS_STATUS_URL, 1))
            # push_notifications_enabled shouldn't get set to False, because this is treated
            # as a transient error.
            self.assertPushNotificationsAre(True)

            # However after an hour has passed without seeing push notifications
            # working, we take the error seriously.
            with time_machine.travel(now() + timedelta(minutes=61), tick=False):
                send_server_data_to_push_bouncer()
                self.assertEqual(
                    "WARNING:zulip.analytics:ConnectionError while trying to connect to push notification bouncer",
                    mock_warning.output[1],
                )
                self.assertTrue(resp.assert_call_count(ANALYTICS_STATUS_URL, 2))
                self.assertPushNotificationsAre(False)

            redis_client.delete(
                redis_utils.REDIS_KEY_PREFIX + PUSH_NOTIFICATIONS_RECENTLY_WORKING_REDIS_KEY
            )

        with (
            responses.RequestsMock() as resp,
            self.assertLogs("zulip.analytics", level="WARNING") as mock_warning,
        ):
            resp.add(responses.GET, ANALYTICS_STATUS_URL, body="This is not JSON")
            Realm.objects.all().update(push_notifications_enabled=True)
            send_server_data_to_push_bouncer()
            self.assertTrue(
                mock_warning.output[0].startswith(
                    f"ERROR:zulip.analytics:Exception communicating with {settings.ZULIP_SERVICES_URL}\nTraceback",
                )
            )
            self.assertTrue(resp.assert_call_count(ANALYTICS_STATUS_URL, 1))
            self.assertPushNotificationsAre(False)

        with responses.RequestsMock() as resp, self.assertLogs("", level="WARNING") as mock_warning:
            resp.add(responses.GET, ANALYTICS_STATUS_URL, body="Server error", status=502)
            Realm.objects.all().update(push_notifications_enabled=True)
            send_server_data_to_push_bouncer()
            self.assertEqual(
                "WARNING:root:Received 502 from push notification bouncer",
                mock_warning.output[0],
            )
            self.assertTrue(resp.assert_call_count(ANALYTICS_STATUS_URL, 1))
            self.assertPushNotificationsAre(True)

        with (
            responses.RequestsMock() as resp,
            self.assertLogs("zulip.analytics", level="WARNING") as mock_warning,
        ):
            Realm.objects.all().update(push_notifications_enabled=True)
            resp.add(
                responses.GET,
                ANALYTICS_STATUS_URL,
                status=401,
                json={"CODE": "UNAUTHORIZED", "msg": "Some problem", "result": "error"},
            )
            send_server_data_to_push_bouncer()
            self.assertIn(
                "WARNING:zulip.analytics:Some problem",
                mock_warning.output[0],
            )
            self.assertTrue(resp.assert_call_count(ANALYTICS_STATUS_URL, 1))
            self.assertPushNotificationsAre(False)

        with (
            responses.RequestsMock() as resp,
            self.assertLogs("zulip.analytics", level="WARNING") as mock_warning,
        ):
            Realm.objects.all().update(push_notifications_enabled=True)
            resp.add(
                responses.GET,
                ANALYTICS_STATUS_URL,
                json={
                    "last_realm_count_id": 0,
                    "last_installation_count_id": 0,
                    "last_realmauditlog_id": 0,
                },
            )
            resp.add(
                responses.POST,
                ANALYTICS_URL,
                status=401,
                json={"CODE": "UNAUTHORIZED", "msg": "Some problem", "result": "error"},
            )
            send_server_data_to_push_bouncer()
            self.assertIn(
                "WARNING:zulip.analytics:Some problem",
                mock_warning.output[0],
            )
            self.assertTrue(resp.assert_call_count(ANALYTICS_URL, 1))
            self.assertPushNotificationsAre(False)

    @activate_push_notification_service(submit_usage_statistics=True)
    @responses.activate
    def test_analytics_api(self) -> None:
        """This is a variant of the below test_push_api, but using the full
        push notification bouncer flow
        """
        assert settings.ZULIP_SERVICES_URL is not None
        ANALYTICS_URL = settings.ZULIP_SERVICES_URL + "/api/v1/remotes/server/analytics"
        ANALYTICS_STATUS_URL = ANALYTICS_URL + "/status"
        user = self.example_user("hamlet")
        end_time = self.TIME_ZERO

        self.add_mock_response()
        # Send any existing data over, so that we can start the test with a "clean" slate
        remote_server = self.server
        assert remote_server is not None
        assert remote_server.last_version is None

        send_server_data_to_push_bouncer()
        self.assertTrue(responses.assert_call_count(ANALYTICS_STATUS_URL, 1))

        audit_log = RealmAuditLog.objects.all().order_by("id").last()
        assert audit_log is not None
        audit_log_max_id = audit_log.id

        remote_server.refresh_from_db()
        assert remote_server.last_version == ZULIP_VERSION

        remote_audit_log_count = RemoteRealmAuditLog.objects.count()

        self.assertEqual(RemoteRealmCount.objects.count(), 0)
        self.assertEqual(RemoteInstallationCount.objects.count(), 0)

        def check_counts(
            analytics_status_mock_request_call_count: int,
            analytics_mock_request_call_count: int,
            remote_realm_count: int,
            remote_installation_count: int,
            remote_realm_audit_log: int,
        ) -> None:
            self.assertTrue(
                responses.assert_call_count(
                    ANALYTICS_STATUS_URL, analytics_status_mock_request_call_count
                )
            )
            self.assertTrue(
                responses.assert_call_count(ANALYTICS_URL, analytics_mock_request_call_count)
            )
            self.assertEqual(RemoteRealmCount.objects.count(), remote_realm_count)
            self.assertEqual(RemoteInstallationCount.objects.count(), remote_installation_count)
            self.assertEqual(
                RemoteRealmAuditLog.objects.count(), remote_audit_log_count + remote_realm_audit_log
            )

        # Create some rows we'll send to remote server
        # LoggingCountStat that should be included;
        # i.e. not in LOGGING_COUNT_STAT_PROPERTIES_NOT_SENT_TO_BOUNCER
        messages_read_logging_stat = LoggingCountStat(
            "messages_read::hour", UserCount, CountStat.HOUR
        )
        RealmCount.objects.create(
            realm=user.realm,
            property=messages_read_logging_stat.property,
            end_time=end_time,
            value=5,
        )
        InstallationCount.objects.create(
            property=messages_read_logging_stat.property,
            end_time=end_time,
            value=5,
        )
        # LoggingCountStat that should not be included;
        # i.e. in LOGGING_COUNT_STAT_PROPERTIES_NOT_SENT_TO_BOUNCER
        invites_sent_logging_stat = LoggingCountStat("invites_sent::day", RealmCount, CountStat.DAY)
        RealmCount.objects.create(
            realm=user.realm,
            property=invites_sent_logging_stat.property,
            end_time=end_time,
            value=5,
        )
        InstallationCount.objects.create(
            property=invites_sent_logging_stat.property,
            end_time=end_time,
            value=5,
        )
        # Event type in SYNCED_BILLING_EVENTS -- should be included
        RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=AuditLogEventType.USER_CREATED,
            event_time=end_time,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user.realm),
                }
            ).decode(),
        )
        # Event type not in SYNCED_BILLING_EVENTS -- should not be included
        RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=AuditLogEventType.REALM_LOGO_CHANGED,
            event_time=end_time,
            extra_data=orjson.dumps({"foo": "bar"}).decode(),
        )
        self.assertEqual(RealmCount.objects.count(), 2)
        self.assertEqual(InstallationCount.objects.count(), 2)
        self.assertEqual(RealmAuditLog.objects.filter(id__gt=audit_log_max_id).count(), 2)

        with self.settings(ANALYTICS_DATA_UPLOAD_LEVEL=AnalyticsDataUploadLevel.BILLING):
            # With this setting, we don't send RealmCounts and InstallationCounts.
            send_server_data_to_push_bouncer()
        check_counts(2, 2, 0, 0, 1)

        with self.settings(ANALYTICS_DATA_UPLOAD_LEVEL=AnalyticsDataUploadLevel.ALL):
            # With ALL data upload enabled, but 'consider_usage_statistics=False',
            # we don't send RealmCount and InstallationCounts.
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
        check_counts(3, 3, 0, 0, 1)

        send_server_data_to_push_bouncer()
        check_counts(4, 4, 1, 1, 1)

        self.assertEqual(
            list(
                RemoteRealm.objects.order_by("id").values(
                    "server_id",
                    "uuid",
                    "uuid_owner_secret",
                    "host",
                    "name",
                    "org_type",
                    "authentication_methods",
                    "realm_date_created",
                    "registration_deactivated",
                    "realm_deactivated",
                    "plan_type",
                    "is_system_bot_realm",
                )
            ),
            [
                {
                    "server_id": self.server.id,
                    "uuid": realm.uuid,
                    "uuid_owner_secret": realm.uuid_owner_secret,
                    "host": realm.host,
                    "name": realm.name,
                    "org_type": realm.org_type,
                    "authentication_methods": realm.authentication_methods_dict(),
                    "realm_date_created": realm.date_created,
                    "registration_deactivated": False,
                    "realm_deactivated": False,
                    "plan_type": RemoteRealm.PLAN_TYPE_SELF_MANAGED,
                    "is_system_bot_realm": realm.string_id == "zulipinternal",
                }
                for realm in Realm.objects.order_by("id")
            ],
        )

        # Modify a realm and verify the remote realm data that should get updated, get updated.
        zephyr_realm = get_realm("zephyr")
        zephyr_original_host = zephyr_realm.host
        zephyr_realm.string_id = "zephyr2"

        zephyr_original_name = zephyr_realm.name
        zephyr_realm.name = "Zephyr2"

        zephyr_original_org_type = zephyr_realm.org_type
        self.assertEqual(zephyr_realm.org_type, Realm.ORG_TYPES["business"]["id"])
        do_change_realm_org_type(
            zephyr_realm, Realm.ORG_TYPES["government"]["id"], acting_user=user
        )

        # date_created can't be updated.
        original_date_created = zephyr_realm.date_created
        zephyr_realm.date_created = now()
        zephyr_realm.save()

        zephyr_original_authentication_methods = zephyr_realm.authentication_methods_dict()
        # Sanity check to make sure the set up is how we think.
        self.assertEqual(zephyr_original_authentication_methods["Email"], True)

        new_auth_method_dict = {
            "Google": False,
            "Email": False,
            "GitHub": False,
            "Apple": False,
            "Dev": True,
            "SAML": True,
            "GitLab": False,
            "OpenID Connect": False,
        }
        do_set_realm_authentication_methods(zephyr_realm, new_auth_method_dict, acting_user=user)

        # Deactivation is synced.
        do_deactivate_realm(
            zephyr_realm, acting_user=None, deactivation_reason="owner_request", email_owners=False
        )

        send_server_data_to_push_bouncer()
        check_counts(5, 5, 1, 1, 7)

        zephyr_remote_realm = RemoteRealm.objects.get(uuid=zephyr_realm.uuid)
        self.assertEqual(zephyr_remote_realm.host, zephyr_realm.host)
        self.assertEqual(zephyr_remote_realm.realm_date_created, original_date_created)
        self.assertEqual(zephyr_remote_realm.realm_deactivated, True)
        self.assertEqual(zephyr_remote_realm.name, zephyr_realm.name)
        self.assertEqual(zephyr_remote_realm.authentication_methods, new_auth_method_dict)
        self.assertEqual(zephyr_remote_realm.org_type, Realm.ORG_TYPES["government"]["id"])

        # Verify the RemoteRealmAuditLog entries created.
        remote_audit_logs = (
            RemoteRealmAuditLog.objects.filter(
                event_type=AuditLogEventType.REMOTE_REALM_VALUE_UPDATED,
                remote_realm=zephyr_remote_realm,
            )
            .order_by("id")
            .values("event_type", "remote_id", "realm_id", "extra_data")
        )

        self.assertEqual(
            list(remote_audit_logs),
            [
                dict(
                    event_type=AuditLogEventType.REMOTE_REALM_VALUE_UPDATED,
                    remote_id=None,
                    realm_id=zephyr_realm.id,
                    extra_data={
                        "attr_name": "host",
                        "old_value": zephyr_original_host,
                        "new_value": zephyr_realm.host,
                    },
                ),
                dict(
                    event_type=AuditLogEventType.REMOTE_REALM_VALUE_UPDATED,
                    remote_id=None,
                    realm_id=zephyr_realm.id,
                    extra_data={
                        "attr_name": "org_type",
                        "old_value": zephyr_original_org_type,
                        "new_value": zephyr_realm.org_type,
                    },
                ),
                dict(
                    event_type=AuditLogEventType.REMOTE_REALM_VALUE_UPDATED,
                    remote_id=None,
                    realm_id=zephyr_realm.id,
                    extra_data={
                        "attr_name": "name",
                        "old_value": zephyr_original_name,
                        "new_value": zephyr_realm.name,
                    },
                ),
                dict(
                    event_type=AuditLogEventType.REMOTE_REALM_VALUE_UPDATED,
                    remote_id=None,
                    realm_id=zephyr_realm.id,
                    extra_data={
                        "attr_name": "authentication_methods",
                        "old_value": zephyr_original_authentication_methods,
                        "new_value": new_auth_method_dict,
                    },
                ),
                dict(
                    event_type=AuditLogEventType.REMOTE_REALM_VALUE_UPDATED,
                    remote_id=None,
                    realm_id=zephyr_realm.id,
                    extra_data={
                        "attr_name": "realm_deactivated",
                        "old_value": False,
                        "new_value": True,
                    },
                ),
            ],
        )

        # Test having no new rows
        send_server_data_to_push_bouncer()
        check_counts(6, 6, 1, 1, 7)

        # Test only having new RealmCount rows
        RealmCount.objects.create(
            realm=user.realm,
            property=messages_read_logging_stat.property,
            end_time=end_time + timedelta(days=1),
            value=6,
        )
        RealmCount.objects.create(
            realm=user.realm,
            property=messages_read_logging_stat.property,
            end_time=end_time + timedelta(days=2),
            value=9,
        )
        send_server_data_to_push_bouncer()
        check_counts(7, 7, 3, 1, 7)

        # Test only having new InstallationCount rows
        InstallationCount.objects.create(
            property=messages_read_logging_stat.property,
            end_time=end_time + timedelta(days=1),
            value=6,
        )
        send_server_data_to_push_bouncer()
        check_counts(8, 8, 3, 2, 7)

        # Test only having new RealmAuditLog rows
        # Non-synced event
        RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=AuditLogEventType.REALM_LOGO_CHANGED,
            event_time=end_time,
            extra_data={"data": "foo"},
        )
        send_server_data_to_push_bouncer()
        check_counts(9, 9, 3, 2, 7)
        # Synced event
        RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=AuditLogEventType.USER_REACTIVATED,
            event_time=end_time,
            extra_data={
                RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user.realm),
            },
        )
        with self.settings(ANALYTICS_DATA_UPLOAD_LEVEL=AnalyticsDataUploadLevel.BASIC):
            # With the BASIC level, RealmAuditLog rows are not sent.
            send_server_data_to_push_bouncer()
        check_counts(10, 10, 3, 2, 7)

        # Now, with ANALYTICS_DATA_UPLOAD_LEVEL back to the baseline for this test,
        # the new RealmAuditLog event will be sent.
        send_server_data_to_push_bouncer()
        check_counts(11, 11, 3, 2, 8)

        # Now create an InstallationCount with a property that's not supposed
        # to be tracked by the remote server - since the bouncer itself tracks
        # the RemoteInstallationCount with this property. We want to verify
        # that the remote server will fail at sending analytics to the bouncer
        # with such an InstallationCount - since syncing it should not be allowed.
        forbidden_installation_count = InstallationCount.objects.create(
            property="mobile_pushes_received::day",
            end_time=end_time,
            value=5,
        )
        with self.assertLogs("zulip.analytics", level="WARNING") as warn_log:
            send_server_data_to_push_bouncer()
        self.assertEqual(
            warn_log.output,
            ["WARNING:zulip.analytics:Invalid property mobile_pushes_received::day"],
        )
        # The analytics endpoint call counts increase by 1, but the actual RemoteCounts remain unchanged,
        # since syncing the data failed.
        check_counts(12, 12, 3, 2, 8)
        forbidden_installation_count.delete()

        (realm_count_data, installation_count_data, realmauditlog_data) = build_analytics_data(
            RealmCount.objects.all(), InstallationCount.objects.all(), RealmAuditLog.objects.all()
        )
        request = AnalyticsRequest.model_construct(
            realm_counts=realm_count_data,
            installation_counts=installation_count_data,
            realmauditlog_rows=realmauditlog_data,
            realms=[],
            version=None,
            merge_base=None,
            api_feature_level=None,
        )
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/server/analytics",
            request.model_dump(
                round_trip=True, exclude={"realms", "version", "merge_base", "api_feature_level"}
            ),
            subdomain="",
        )
        self.assert_json_error(result, "Data is out of order.")

        # Adjust the id of all existing rows so that they get re-sent.
        # This is equivalent to running `./manage.py clear_analytics_tables`
        RealmCount.objects.all().update(id=F("id") + RealmCount.objects.latest("id").id)
        InstallationCount.objects.all().update(
            id=F("id") + InstallationCount.objects.latest("id").id
        )
        with self.assertLogs(level="WARNING") as warn_log:
            send_server_data_to_push_bouncer()
        self.assertEqual(
            warn_log.output,
            [
                f"WARNING:root:Dropped 3 duplicated rows while saving 3 rows of zilencer_remoterealmcount for server demo.example.com/{self.server_uuid}",
                f"WARNING:root:Dropped 2 duplicated rows while saving 2 rows of zilencer_remoteinstallationcount for server demo.example.com/{self.server_uuid}",
            ],
        )
        # Only the request counts go up -- all of the other rows' duplicates are dropped
        check_counts(13, 13, 3, 2, 8)

        # Test that only valid org_type values are accepted - integers defined in OrgTypeEnum.
        realms_data = get_realms_info_for_push_bouncer()
        # Not a valid org_type value:
        realms_data[0].org_type = 11

        request = AnalyticsRequest.model_construct(
            realm_counts=[],
            installation_counts=[],
            realmauditlog_rows=[],
            realms=realms_data,
            version=None,
            merge_base=None,
            api_feature_level=None,
        )
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/server/analytics",
            request.model_dump(
                round_trip=True, exclude={"version", "merge_base", "api_feature_level"}
            ),
            subdomain="",
        )
        self.assert_json_error(
            result, 'Invalid realms[0]["org_type"]: Value error, Not a valid org_type value'
        )

    @activate_push_notification_service(submit_usage_statistics=True)
    @responses.activate
    def test_analytics_api_foreign_keys_to_remote_realm(self) -> None:
        self.add_mock_response()

        user = self.example_user("hamlet")
        end_time = self.TIME_ZERO

        # Create some rows we'll send to remote server
        messages_read_logging_stat = LoggingCountStat(
            "messages_read::hour", UserCount, CountStat.HOUR
        )
        realm_count = RealmCount.objects.create(
            realm=user.realm,
            property=messages_read_logging_stat.property,
            end_time=end_time,
            value=5,
        )
        installation_count = InstallationCount.objects.create(
            property=messages_read_logging_stat.property,
            end_time=end_time,
            value=5,
        )
        realm_audit_log = RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=AuditLogEventType.USER_CREATED,
            event_time=end_time,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user.realm),
                }
            ).decode(),
        )
        realm_count_data, installation_count_data, realmauditlog_data = build_analytics_data(
            RealmCount.objects.all(), InstallationCount.objects.all(), RealmAuditLog.objects.all()
        )

        # This first post should fail because of excessive audit log event types.
        request = AnalyticsRequest.model_construct(
            realm_counts=realm_count_data,
            installation_counts=installation_count_data,
            realmauditlog_rows=realmauditlog_data,
            realms=[],
            version=None,
            merge_base=None,
            api_feature_level=None,
        )
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/server/analytics",
            request.model_dump(
                round_trip=True, exclude={"version", "merge_base", "api_feature_level"}
            ),
            subdomain="",
        )
        self.assert_json_error(result, "Invalid event type.")

        # Start again only using synced billing events.
        realm_count_data, installation_count_data, realmauditlog_data = build_analytics_data(
            RealmCount.objects.all(),
            InstallationCount.objects.all(),
            RealmAuditLog.objects.filter(event_type__in=RemoteRealmAuditLog.SYNCED_BILLING_EVENTS),
        )

        # Send the data to the bouncer without any realms data. This should lead
        # to successful saving of the data, but with the remote_realm foreign key
        # set to NULL.
        request = AnalyticsRequest.model_construct(
            realm_counts=realm_count_data,
            installation_counts=installation_count_data,
            realmauditlog_rows=realmauditlog_data,
            realms=[],
            version=None,
            merge_base=None,
            api_feature_level=None,
        )
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/server/analytics",
            request.model_dump(
                round_trip=True, exclude={"version", "merge_base", "api_feature_level"}
            ),
            subdomain="",
        )
        self.assert_json_success(result)
        remote_realm_count = RemoteRealmCount.objects.latest("id")
        remote_installation_count = RemoteInstallationCount.objects.latest("id")
        remote_realm_audit_log = RemoteRealmAuditLog.objects.latest("id")

        self.assertEqual(remote_realm_count.remote_id, realm_count.id)
        self.assertEqual(remote_realm_count.remote_realm, None)
        self.assertEqual(remote_installation_count.remote_id, installation_count.id)
        # InstallationCount/RemoteInstallationCount don't have realm/remote_realm foreign
        # keys, because they're aggregated over all realms.

        self.assertEqual(remote_realm_audit_log.remote_id, realm_audit_log.id)
        self.assertEqual(remote_realm_audit_log.remote_realm, None)

        send_server_data_to_push_bouncer()

        remote_realm_count.refresh_from_db()
        remote_installation_count.refresh_from_db()
        remote_realm_audit_log.refresh_from_db()

        remote_realm = RemoteRealm.objects.get(uuid=user.realm.uuid)

        self.assertEqual(remote_realm_count.remote_realm, remote_realm)
        self.assertEqual(remote_realm_audit_log.remote_realm, remote_realm)

        current_remote_realm_count_amount = RemoteRealmCount.objects.count()
        current_remote_realm_audit_log_amount = RemoteRealmAuditLog.objects.count()

        # Now create and send new data (including realm info) and verify it has .remote_realm
        # set as it should.
        RealmCount.objects.create(
            realm=user.realm,
            property=messages_read_logging_stat.property,
            end_time=end_time + timedelta(days=1),
            value=6,
        )
        InstallationCount.objects.create(
            property=messages_read_logging_stat.property,
            end_time=end_time + timedelta(days=1),
            value=6,
        )
        RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=AuditLogEventType.USER_CREATED,
            event_time=end_time,
            extra_data={
                RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user.realm),
            },
        )
        send_server_data_to_push_bouncer()

        # Make sure new data was created, so that we're actually testing what we think.
        self.assertEqual(RemoteRealmCount.objects.count(), current_remote_realm_count_amount + 1)
        self.assertEqual(
            RemoteRealmAuditLog.objects.count(), current_remote_realm_audit_log_amount + 1
        )

        for remote_realm_count in RemoteRealmCount.objects.filter(realm_id=user.realm.id):
            self.assertEqual(remote_realm_count.remote_realm, remote_realm)
        for remote_realm_audit_log in RemoteRealmAuditLog.objects.filter(realm_id=user.realm.id):
            self.assertEqual(remote_realm_audit_log.remote_realm, remote_realm)

    @activate_push_notification_service(submit_usage_statistics=True)
    @responses.activate
    def test_analytics_api_invalid(self) -> None:
        """This is a variant of the below test_push_api, but using the full
        push notification bouncer flow
        """
        self.add_mock_response()
        user = self.example_user("hamlet")
        end_time = self.TIME_ZERO

        realm_stat = LoggingCountStat("invalid count stat", RealmCount, CountStat.DAY)
        RealmCount.objects.create(
            realm=user.realm, property=realm_stat.property, end_time=end_time, value=5
        )

        self.assertEqual(RealmCount.objects.count(), 1)

        self.assertEqual(RemoteRealmCount.objects.count(), 0)
        with self.assertLogs("zulip.analytics", level="WARNING") as m:
            send_server_data_to_push_bouncer()
        self.assertEqual(m.output, ["WARNING:zulip.analytics:Invalid property invalid count stat"])
        self.assertEqual(RemoteRealmCount.objects.count(), 0)

    @activate_push_notification_service()
    @responses.activate
    def test_remote_realm_duplicate_uuid(self) -> None:
        """
        Tests for a case where a RemoteRealm with a certain uuid is already registered for one server,
        and then another server tries to register the same uuid. This generally shouldn't happen,
        because export->import of a realm should re-generate the uuid, but we should have error
        handling for this edge case nonetheless.
        """

        original_server = RemoteZulipServer.objects.get(uuid=self.server.uuid)
        # Start by deleting existing registration, to have a clean slate.
        RemoteRealm.objects.all().delete()

        second_server = RemoteZulipServer.objects.create(
            uuid=uuid.uuid4(),
            api_key="magic_secret_api_key2",
            hostname="demo2.example.com",
            last_updated=now(),
        )

        self.add_mock_response()
        user = self.example_user("hamlet")
        realm = user.realm

        RemoteRealm.objects.create(
            server=second_server,
            uuid=realm.uuid,
            uuid_owner_secret=realm.uuid_owner_secret,
            host=realm.host,
            realm_date_created=realm.date_created,
            registration_deactivated=False,
            realm_deactivated=False,
            plan_type=RemoteRealm.PLAN_TYPE_SELF_MANAGED,
        )

        with (
            self.assertLogs("zulip.analytics", level="WARNING") as mock_log_host,
            self.assertLogs("zilencer.views") as mock_log_bouncer,
        ):
            send_server_data_to_push_bouncer()
        self.assertEqual(
            mock_log_host.output, ["WARNING:zulip.analytics:Duplicate registration detected."]
        )
        self.assertIn(
            "INFO:zilencer.views:"
            f"update_remote_realm_data_for_server:server:{original_server.id}:IntegrityError creating RemoteRealm rows:",
            mock_log_bouncer.output[0],
        )

    # Servers on Zulip 2.0.6 and earlier only send realm_counts and installation_counts data,
    # and don't send realmauditlog_rows. Make sure that continues to work.
    @activate_push_notification_service()
    @responses.activate
    def test_old_two_table_format(self) -> None:
        self.add_mock_response()
        # Send fixture generated with Zulip 2.0 code
        send_to_push_bouncer(
            "POST",
            "server/analytics",
            {
                "realm_counts": '[{"id":1,"property":"messages_sent:is_bot:hour","subgroup":"false","end_time":574300800.0,"value":5,"realm":2}]',
                "installation_counts": "[]",
                "version": '"2.0.6+git"',
            },
        )
        assert settings.ZULIP_SERVICES_URL is not None
        ANALYTICS_URL = settings.ZULIP_SERVICES_URL + "/api/v1/remotes/server/analytics"
        self.assertTrue(responses.assert_call_count(ANALYTICS_URL, 1))
        self.assertEqual(RemoteRealmCount.objects.count(), 1)
        self.assertEqual(RemoteInstallationCount.objects.count(), 0)
        self.assertEqual(RemoteRealmAuditLog.objects.count(), 0)

    # Make sure we aren't sending data we don't mean to, even if we don't store it.
    @activate_push_notification_service()
    @responses.activate
    def test_only_sending_intended_realmauditlog_data(self) -> None:
        self.add_mock_response()
        user = self.example_user("hamlet")
        # Event type in SYNCED_BILLING_EVENTS -- should be included
        RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=AuditLogEventType.USER_REACTIVATED,
            event_time=self.TIME_ZERO,
            extra_data={
                RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user.realm),
            },
        )
        # Event type not in SYNCED_BILLING_EVENTS -- should not be included
        RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=AuditLogEventType.REALM_LOGO_CHANGED,
            event_time=self.TIME_ZERO,
            extra_data=orjson.dumps({"foo": "bar"}).decode(),
        )

        # send_server_data_to_push_bouncer calls send_to_push_bouncer twice.
        # We need to distinguish the first and second calls.
        first_call = True

        def check_for_unwanted_data(*args: Any) -> Any:
            nonlocal first_call
            if first_call:
                first_call = False
            else:
                # Test that we're respecting SYNCED_BILLING_EVENTS
                self.assertIn(f'"event_type":{AuditLogEventType.USER_REACTIVATED}', str(args))
                self.assertNotIn(f'"event_type":{AuditLogEventType.REALM_LOGO_CHANGED}', str(args))
                # Test that we're respecting REALMAUDITLOG_PUSHED_FIELDS
                self.assertIn("backfilled", str(args))
                self.assertNotIn("modified_user", str(args))
            return send_to_push_bouncer(*args)

        with mock.patch(
            "zerver.lib.remote_server.send_to_push_bouncer", side_effect=check_for_unwanted_data
        ):
            send_server_data_to_push_bouncer()

    @activate_push_notification_service()
    @responses.activate
    def test_realmauditlog_data_mapping(self) -> None:
        self.add_mock_response()
        user = self.example_user("hamlet")
        user_count = realm_user_count_by_role(user.realm)
        log_entry = RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            backfilled=True,
            event_type=AuditLogEventType.USER_REACTIVATED,
            event_time=self.TIME_ZERO,
            extra_data=orjson.dumps({RealmAuditLog.ROLE_COUNT: user_count}).decode(),
        )
        send_server_data_to_push_bouncer()
        remote_log_entry = RemoteRealmAuditLog.objects.order_by("id").last()
        assert remote_log_entry is not None
        self.assertEqual(str(remote_log_entry.server.uuid), self.server_uuid)
        self.assertEqual(remote_log_entry.remote_id, log_entry.id)
        self.assertEqual(remote_log_entry.event_time, self.TIME_ZERO)
        self.assertEqual(remote_log_entry.backfilled, True)
        assert remote_log_entry.extra_data is not None
        self.assertEqual(remote_log_entry.extra_data, {RealmAuditLog.ROLE_COUNT: user_count})
        self.assertEqual(remote_log_entry.event_type, AuditLogEventType.USER_REACTIVATED)

    # This verifies that the bouncer is backwards-compatible with remote servers using
    # TextField to store extra_data.
    @activate_push_notification_service()
    @responses.activate
    def test_realmauditlog_string_extra_data(self) -> None:
        self.add_mock_response()

        def verify_request_with_overridden_extra_data(
            request_extra_data: object,
            *,
            expected_extra_data: object = None,
            skip_audit_log_check: bool = False,
        ) -> None:
            user = self.example_user("hamlet")
            log_entry = RealmAuditLog.objects.create(
                realm=user.realm,
                modified_user=user,
                event_type=AuditLogEventType.USER_REACTIVATED,
                event_time=self.TIME_ZERO,
                extra_data=orjson.dumps(
                    {
                        RealmAuditLog.ROLE_COUNT: {
                            RealmAuditLog.ROLE_COUNT_HUMANS: {},
                        }
                    }
                ).decode(),
            )

            # We use this to patch send_to_push_bouncer so that extra_data in the
            # legacy format gets sent to the bouncer.
            def transform_realmauditlog_extra_data(
                method: str,
                endpoint: str,
                post_data: bytes | Mapping[str, str | int | None | bytes],
                extra_headers: Mapping[str, str] = {},
            ) -> dict[str, Any]:
                if endpoint == "server/analytics":
                    assert isinstance(post_data, dict)
                    assert isinstance(post_data["realmauditlog_rows"], str)
                    original_data = orjson.loads(post_data["realmauditlog_rows"])
                    # We replace the extra_data with another fake example to verify that
                    # the bouncer actually gets requested with extra_data being string
                    new_data = [{**row, "extra_data": request_extra_data} for row in original_data]
                    post_data["realmauditlog_rows"] = orjson.dumps(new_data).decode()
                return send_to_push_bouncer(method, endpoint, post_data, extra_headers)

            with mock.patch(
                "zerver.lib.remote_server.send_to_push_bouncer",
                side_effect=transform_realmauditlog_extra_data,
            ):
                send_server_data_to_push_bouncer()

            if skip_audit_log_check:
                return

            remote_log_entry = RemoteRealmAuditLog.objects.order_by("id").last()
            assert remote_log_entry is not None
            self.assertEqual(str(remote_log_entry.server.uuid), self.server_uuid)
            self.assertEqual(remote_log_entry.remote_id, log_entry.id)
            self.assertEqual(remote_log_entry.event_time, self.TIME_ZERO)
            self.assertEqual(remote_log_entry.extra_data, expected_extra_data)

        # Pre-migration extra_data
        verify_request_with_overridden_extra_data(
            request_extra_data=orjson.dumps(
                {
                    RealmAuditLog.ROLE_COUNT: {
                        RealmAuditLog.ROLE_COUNT_HUMANS: {},
                    }
                }
            ).decode(),
            expected_extra_data={
                RealmAuditLog.ROLE_COUNT: {
                    RealmAuditLog.ROLE_COUNT_HUMANS: {},
                }
            },
        )
        verify_request_with_overridden_extra_data(request_extra_data=None, expected_extra_data={})
        # Post-migration extra_data
        verify_request_with_overridden_extra_data(
            request_extra_data={
                RealmAuditLog.ROLE_COUNT: {
                    RealmAuditLog.ROLE_COUNT_HUMANS: {},
                }
            },
            expected_extra_data={
                RealmAuditLog.ROLE_COUNT: {
                    RealmAuditLog.ROLE_COUNT_HUMANS: {},
                }
            },
        )
        verify_request_with_overridden_extra_data(
            request_extra_data={},
            expected_extra_data={},
        )
        # Invalid extra_data
        with self.assertLogs("zulip.analytics", level="WARNING") as m:
            verify_request_with_overridden_extra_data(
                request_extra_data="{malformedjson:",
                skip_audit_log_check=True,
            )
        self.assertIn("Malformed audit log data", m.output[0])

    @activate_push_notification_service()
    @responses.activate
    def test_realm_properties_after_send_analytics(self) -> None:
        self.add_mock_response()

        with (
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.get_customer", return_value=None
            ) as m,
            mock.patch(
                "corporate.lib.stripe.RemoteServerBillingSession.current_count_for_billed_licenses",
                return_value=10,
            ),
        ):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            m.assert_called()
            realms = Realm.objects.all()
            for realm in realms:
                self.assertEqual(realm.push_notifications_enabled, True)
                self.assertEqual(realm.push_notifications_enabled_end_timestamp, None)

        with (
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.get_customer", return_value=None
            ) as m,
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
                return_value=11,
            ),
        ):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            m.assert_called()
            realms = Realm.objects.all()
            for realm in realms:
                self.assertEqual(realm.push_notifications_enabled, False)
                self.assertEqual(realm.push_notifications_enabled_end_timestamp, None)

        dummy_customer = mock.MagicMock()
        with (
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.get_customer",
                return_value=dummy_customer,
            ),
            mock.patch("corporate.lib.stripe.get_current_plan_by_customer", return_value=None) as m,
        ):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            m.assert_called()
            realms = Realm.objects.all()
            for realm in realms:
                self.assertEqual(realm.push_notifications_enabled, True)
                self.assertEqual(realm.push_notifications_enabled_end_timestamp, None)

        dummy_customer = mock.MagicMock()
        with (
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.get_customer",
                return_value=dummy_customer,
            ),
            mock.patch("corporate.lib.stripe.get_current_plan_by_customer", return_value=None) as m,
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
                return_value=11,
            ),
        ):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            m.assert_called()
            realms = Realm.objects.all()
            for realm in realms:
                self.assertEqual(realm.push_notifications_enabled, False)
                self.assertEqual(realm.push_notifications_enabled_end_timestamp, None)

        RemoteRealm.objects.filter(server=self.server).update(
            plan_type=RemoteRealm.PLAN_TYPE_COMMUNITY
        )

        with (
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.get_customer",
                return_value=dummy_customer,
            ),
            mock.patch("corporate.lib.stripe.get_current_plan_by_customer", return_value=None),
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses"
            ) as m,
        ):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            m.assert_not_called()
            realms = Realm.objects.all()
            for realm in realms:
                self.assertEqual(realm.push_notifications_enabled, True)
                self.assertEqual(realm.push_notifications_enabled_end_timestamp, None)

        # Reset the plan type to test remaining cases.
        RemoteRealm.objects.filter(server=self.server).update(
            plan_type=RemoteRealm.PLAN_TYPE_SELF_MANAGED
        )

        dummy_customer_plan = mock.MagicMock()
        dummy_customer_plan.status = CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE
        dummy_date = datetime(year=2023, month=12, day=3, tzinfo=timezone.utc)
        with (
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.get_customer",
                return_value=dummy_customer,
            ),
            mock.patch(
                "corporate.lib.stripe.get_current_plan_by_customer",
                return_value=dummy_customer_plan,
            ),
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
                return_value=11,
            ),
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.get_next_billing_cycle",
                return_value=dummy_date,
            ) as m,
            self.assertLogs("zulip.analytics", level="INFO") as info_log,
        ):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            m.assert_called()
            realms = Realm.objects.all()
            for realm in realms:
                self.assertEqual(realm.push_notifications_enabled, True)
                self.assertEqual(
                    realm.push_notifications_enabled_end_timestamp,
                    dummy_date,
                )
            self.assertIn(
                "INFO:zulip.analytics:Reported 0 records",
                info_log.output[0],
            )

        with (
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.get_customer",
                return_value=dummy_customer,
            ),
            mock.patch(
                "corporate.lib.stripe.get_current_plan_by_customer",
                return_value=dummy_customer_plan,
            ),
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
                side_effect=MissingDataError,
            ),
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.get_next_billing_cycle",
                return_value=dummy_date,
            ) as m,
            self.assertLogs("zulip.analytics", level="INFO") as info_log,
        ):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            m.assert_called()
            realms = Realm.objects.all()
            for realm in realms:
                self.assertEqual(realm.push_notifications_enabled, True)
                self.assertEqual(
                    realm.push_notifications_enabled_end_timestamp,
                    dummy_date,
                )
            self.assertIn(
                "INFO:zulip.analytics:Reported 0 records",
                info_log.output[0],
            )

        with (
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.get_customer",
                return_value=dummy_customer,
            ),
            mock.patch(
                "corporate.lib.stripe.get_current_plan_by_customer",
                return_value=dummy_customer_plan,
            ),
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
                return_value=10,
            ),
        ):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            m.assert_called()
            realms = Realm.objects.all()
            for realm in realms:
                self.assertEqual(realm.push_notifications_enabled, True)
                self.assertEqual(
                    realm.push_notifications_enabled_end_timestamp,
                    None,
                )

        dummy_customer_plan = mock.MagicMock()
        dummy_customer_plan.status = CustomerPlan.ACTIVE
        with (
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.get_customer",
                return_value=dummy_customer,
            ),
            mock.patch(
                "corporate.lib.stripe.get_current_plan_by_customer",
                return_value=dummy_customer_plan,
            ),
            self.assertLogs("zulip.analytics", level="INFO") as info_log,
        ):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            m.assert_called()
            realms = Realm.objects.all()
            for realm in realms:
                self.assertEqual(realm.push_notifications_enabled, True)
                self.assertEqual(
                    realm.push_notifications_enabled_end_timestamp,
                    None,
                )
            self.assertIn(
                "INFO:zulip.analytics:Reported 0 records",
                info_log.output[0],
            )

        # Remote realm is on an inactive plan. Remote server on active plan.
        # ACTIVE plan takes precedence.
        dummy_remote_realm_customer = mock.MagicMock()
        dummy_remote_server_customer = mock.MagicMock()
        dummy_remote_server_customer_plan = mock.MagicMock()
        dummy_remote_server_customer_plan.status = CustomerPlan.ACTIVE

        def get_current_plan_by_customer(customer: mock.MagicMock) -> mock.MagicMock | None:
            assert customer in [dummy_remote_realm_customer, dummy_remote_server_customer]
            if customer == dummy_remote_server_customer:
                return dummy_remote_server_customer_plan
            return None

        with (
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.get_customer",
                return_value=dummy_remote_realm_customer,
            ),
            mock.patch(
                "corporate.lib.stripe.RemoteServerBillingSession.get_customer",
                return_value=dummy_remote_server_customer,
            ),
            mock.patch(
                "corporate.lib.stripe.RemoteServerBillingSession.sync_license_ledger_if_needed"
            ),
            mock.patch(
                "corporate.lib.stripe.get_current_plan_by_customer",
                side_effect=get_current_plan_by_customer,
            ) as m,
        ):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            m.assert_called()
            realms = Realm.objects.all()
            for realm in realms:
                self.assertEqual(realm.push_notifications_enabled, True)
                self.assertEqual(
                    realm.push_notifications_enabled_end_timestamp,
                    None,
                )

        with (
            mock.patch("zerver.lib.remote_server.send_to_push_bouncer") as m,
            self.assertLogs("zulip.analytics", level="WARNING") as exception_log,
        ):
            get_response = {
                "last_realm_count_id": 0,
                "last_installation_count_id": 0,
                "last_realmauditlog_id": 0,
            }

            def mock_send_to_push_bouncer_response(method: str, *args: Any) -> dict[str, int]:
                if method == "POST":
                    raise PushNotificationBouncerRetryLaterError("Some problem")
                return get_response

            m.side_effect = mock_send_to_push_bouncer_response

            send_server_data_to_push_bouncer(consider_usage_statistics=False)

            realms = Realm.objects.all()
            for realm in realms:
                self.assertFalse(realm.push_notifications_enabled)
        self.assertEqual(
            exception_log.output,
            ["WARNING:zulip.analytics:Some problem"],
        )

        send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.assertEqual(
            list(
                RemoteRealm.objects.order_by("id").values(
                    "server_id",
                    "uuid",
                    "uuid_owner_secret",
                    "host",
                    "realm_date_created",
                    "registration_deactivated",
                    "realm_deactivated",
                    "plan_type",
                )
            ),
            [
                {
                    "server_id": self.server.id,
                    "uuid": realm.uuid,
                    "uuid_owner_secret": realm.uuid_owner_secret,
                    "host": realm.host,
                    "realm_date_created": realm.date_created,
                    "registration_deactivated": False,
                    "realm_deactivated": False,
                    "plan_type": RemoteRealm.PLAN_TYPE_SELF_MANAGED,
                }
                for realm in Realm.objects.order_by("id")
            ],
        )

    @activate_push_notification_service()
    @responses.activate
    def test_deleted_realm(self) -> None:
        self.add_mock_response()
        logger = logging.getLogger("zulip.analytics")

        realm_info = get_realms_info_for_push_bouncer()

        # Hard-delete a realm to test the non existent realm uuid case.
        zephyr_realm = get_realm("zephyr")
        assert zephyr_realm is not None
        deleted_realm_uuid = zephyr_realm.uuid
        zephyr_realm.delete()

        # This mock causes us to still send data to the bouncer as if the realm existed,
        # causing the bouncer to include its corresponding info in the response. Through
        # that, we're testing our graceful handling of seeing a non-existent realm uuid
        # in that response.
        with (
            mock.patch(
                "zerver.lib.remote_server.get_realms_info_for_push_bouncer", return_value=realm_info
            ) as m,
            self.assertLogs(logger, level="WARNING") as analytics_logger,
        ):
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            m.assert_called()
            realms = Realm.objects.all()
            for realm in realms:
                self.assertEqual(realm.push_notifications_enabled, True)
                self.assertEqual(realm.push_notifications_enabled_end_timestamp, None)

        self.assertEqual(
            analytics_logger.output,
            [
                "WARNING:zulip.analytics:"
                f"Received unexpected realm UUID from bouncer {deleted_realm_uuid}"
            ],
        )

        # Now we want to test the other side of this - bouncer's handling
        # of a deleted realm.
        with (
            self.captureOnCommitCallbacks(execute=True),
            self.assertLogs(logger, level="WARNING") as analytics_logger,
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.on_paid_plan", return_value=True
            ),
        ):
            # This time the logger shouldn't get triggered - because the bouncer doesn't
            # include .realm_locally_deleted realms in its response.
            # Note: This is hacky, because until Python 3.10 we don't have access to
            # assertNoLogs - and regular assertLogs demands that the logger gets triggered.
            # So we do a dummy warning ourselves here, to satisfy it.
            # TODO: Replace this with assertNoLogs once we fully upgrade to Python 3.10.
            logger.warning("Dummy warning")
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
        remote_realm_for_deleted_realm = RemoteRealm.objects.get(uuid=deleted_realm_uuid)

        self.assertEqual(remote_realm_for_deleted_realm.registration_deactivated, False)
        self.assertEqual(remote_realm_for_deleted_realm.realm_locally_deleted, True)
        self.assertEqual(analytics_logger.output, ["WARNING:zulip.analytics:Dummy warning"])

        audit_log = RemoteRealmAuditLog.objects.latest("id")
        self.assertEqual(audit_log.event_type, AuditLogEventType.REMOTE_REALM_LOCALLY_DELETED)
        self.assertEqual(audit_log.remote_realm, remote_realm_for_deleted_realm)

        from django.core.mail import outbox

        email = outbox[-1]
        self.assert_length(email.to, 1)
        self.assertEqual(email.to[0], "sales@zulip.com")

        billing_session = RemoteRealmBillingSession(remote_realm=remote_realm_for_deleted_realm)
        self.assertIn(
            f"Support URL: {billing_session.support_url()}",
            email.body,
        )
        self.assertIn(
            f"Internal billing notice for {billing_session.billing_entity_display_name}.",
            email.body,
        )
        self.assertIn(
            "Investigate why remote realm is marked as locally deleted when it's on a paid plan.",
            email.body,
        )
        self.assertEqual(
            f"{billing_session.billing_entity_display_name} on paid plan marked as locally deleted",
            email.subject,
        )

        # Restore the deleted realm to verify that the bouncer correctly handles that
        # by toggling off .realm_locally_deleted.
        restored_zephyr_realm = do_create_realm("zephyr", "Zephyr")
        restored_zephyr_realm.uuid = deleted_realm_uuid
        restored_zephyr_realm.save()

        send_server_data_to_push_bouncer(consider_usage_statistics=False)
        remote_realm_for_deleted_realm.refresh_from_db()
        self.assertEqual(remote_realm_for_deleted_realm.realm_locally_deleted, False)

        audit_log = RemoteRealmAuditLog.objects.latest("id")
        self.assertEqual(
            audit_log.event_type, AuditLogEventType.REMOTE_REALM_LOCALLY_DELETED_RESTORED
        )
        self.assertEqual(audit_log.remote_realm, remote_realm_for_deleted_realm)
