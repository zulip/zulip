import uuid
from datetime import datetime, timedelta, timezone
from unittest import mock

from django.utils.timezone import now as timezone_now

from corporate.lib.activity import get_remote_server_audit_logs
from corporate.lib.stripe import add_months
from corporate.models.customers import Customer
from corporate.models.licenses import LicenseLedger
from corporate.models.plans import CustomerPlan
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Client, UserActivity, UserProfile
from zerver.models.realm_audit_logs import AuditLogEventType
from zilencer.models import (
    RemoteRealm,
    RemoteRealmAuditLog,
    RemoteZulipServer,
    RemoteZulipServerAuditLog,
    get_remote_customer_user_count,
    get_remote_server_guest_and_non_guest_count,
)

event_time = timezone_now() - timedelta(days=3)
data_list = [
    {
        "server_id": 1,
        "realm_id": 1,
        "event_type": AuditLogEventType.USER_CREATED,
        "event_time": event_time,
        "extra_data": {
            RemoteRealmAuditLog.ROLE_COUNT: {
                RemoteRealmAuditLog.ROLE_COUNT_HUMANS: {
                    UserProfile.ROLE_REALM_ADMINISTRATOR: 10,
                    UserProfile.ROLE_REALM_OWNER: 10,
                    UserProfile.ROLE_MODERATOR: 10,
                    UserProfile.ROLE_MEMBER: 10,
                    UserProfile.ROLE_GUEST: 10,
                }
            }
        },
    },
    {
        "server_id": 1,
        "realm_id": 1,
        "event_type": AuditLogEventType.USER_ROLE_CHANGED,
        "event_time": event_time,
        "extra_data": {
            RemoteRealmAuditLog.ROLE_COUNT: {
                RemoteRealmAuditLog.ROLE_COUNT_HUMANS: {
                    UserProfile.ROLE_REALM_ADMINISTRATOR: 20,
                    UserProfile.ROLE_REALM_OWNER: 0,
                    UserProfile.ROLE_MODERATOR: 0,
                    UserProfile.ROLE_MEMBER: 20,
                    UserProfile.ROLE_GUEST: 10,
                }
            }
        },
    },
    {
        "server_id": 1,
        "realm_id": 2,
        "event_type": AuditLogEventType.USER_CREATED,
        "event_time": event_time,
        "extra_data": {
            RemoteRealmAuditLog.ROLE_COUNT: {
                RemoteRealmAuditLog.ROLE_COUNT_HUMANS: {
                    UserProfile.ROLE_REALM_ADMINISTRATOR: 10,
                    UserProfile.ROLE_REALM_OWNER: 10,
                    UserProfile.ROLE_MODERATOR: 0,
                    UserProfile.ROLE_MEMBER: 10,
                    UserProfile.ROLE_GUEST: 5,
                }
            }
        },
    },
    {
        "server_id": 1,
        "realm_id": 2,
        "event_type": AuditLogEventType.USER_CREATED,
        "event_time": event_time,
        "extra_data": {},
    },
    {
        "server_id": 1,
        "realm_id": 3,
        "event_type": AuditLogEventType.USER_CREATED,
        "event_time": event_time,
        "extra_data": {
            RemoteRealmAuditLog.ROLE_COUNT: {
                RemoteRealmAuditLog.ROLE_COUNT_HUMANS: {
                    UserProfile.ROLE_REALM_ADMINISTRATOR: 1,
                    UserProfile.ROLE_REALM_OWNER: 1,
                    UserProfile.ROLE_MODERATOR: 1,
                    UserProfile.ROLE_MEMBER: 1,
                    UserProfile.ROLE_GUEST: 1,
                }
            }
        },
    },
    {
        "server_id": 1,
        "realm_id": 3,
        "event_type": AuditLogEventType.USER_DEACTIVATED,
        "event_time": event_time + timedelta(seconds=1),
        "extra_data": {
            RemoteRealmAuditLog.ROLE_COUNT: {
                RemoteRealmAuditLog.ROLE_COUNT_HUMANS: {
                    UserProfile.ROLE_REALM_ADMINISTRATOR: 1,
                    UserProfile.ROLE_REALM_OWNER: 1,
                    UserProfile.ROLE_MODERATOR: 1,
                    UserProfile.ROLE_MEMBER: 0,
                    UserProfile.ROLE_GUEST: 1,
                }
            }
        },
    },
]


class ActivityTest(ZulipTestCase):
    @mock.patch("stripe.Customer.list", return_value=[])
    def test_activity(self, unused_mock: mock.Mock) -> None:
        self.login("hamlet")
        client, _ = Client.objects.get_or_create(name="website")
        query = "/json/messages/flags"
        last_visit = timezone_now()
        count = 150
        for activity_user_profile in UserProfile.objects.all():
            UserActivity.objects.get_or_create(
                user_profile=activity_user_profile,
                client=client,
                query=query,
                count=count,
                last_visit=last_visit,
            )

        # Fails when not staff
        result = self.client_get("/activity")
        self.assertEqual(result.status_code, 302)

        user_profile = self.example_user("hamlet")
        user_profile.is_staff = True
        user_profile.save(update_fields=["is_staff"])

        with self.assert_database_query_count(11):
            result = self.client_get("/activity")
            self.assertEqual(result.status_code, 200)

        # Add data for remote activity page
        remote_realm = RemoteRealm.objects.get(name="Lear & Co.")
        customer = Customer.objects.create(remote_realm=remote_realm)
        plan = CustomerPlan.objects.create(
            customer=customer,
            billing_cycle_anchor=timezone_now(),
            billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
            tier=CustomerPlan.TIER_SELF_HOSTED_BUSINESS,
            price_per_license=8000,
            next_invoice_date=add_months(timezone_now(), 12),
        )
        LicenseLedger.objects.create(
            licenses=10,
            licenses_at_next_renewal=10,
            event_time=timezone_now(),
            is_renewal=True,
            plan=plan,
        )
        server = RemoteZulipServer.objects.create(
            uuid=str(uuid.uuid4()),
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            contact_email="email@example.com",
        )
        RemoteZulipServerAuditLog.objects.create(
            event_type=AuditLogEventType.REMOTE_SERVER_CREATED,
            server=server,
            event_time=server.last_updated,
        )
        extra_data = {
            RemoteRealmAuditLog.ROLE_COUNT: {
                RemoteRealmAuditLog.ROLE_COUNT_HUMANS: {
                    UserProfile.ROLE_REALM_ADMINISTRATOR: 1,
                    UserProfile.ROLE_REALM_OWNER: 1,
                    UserProfile.ROLE_MODERATOR: 1,
                    UserProfile.ROLE_MEMBER: 1,
                    UserProfile.ROLE_GUEST: 1,
                }
            }
        }
        RemoteRealmAuditLog.objects.create(
            server=server,
            realm_id=10,
            event_type=AuditLogEventType.USER_CREATED,
            event_time=timezone_now() - timedelta(days=1),
            extra_data=extra_data,
        )
        with self.assert_database_query_count(10):
            result = self.client_get("/activity/remote")
            self.assertEqual(result.status_code, 200)

        with self.assert_database_query_count(5):
            result = self.client_get("/activity/integrations")
            self.assertEqual(result.status_code, 200)

        with self.assert_database_query_count(7):
            result = self.client_get("/realm_activity/zulip/")
            self.assertEqual(result.status_code, 200)

        iago = self.example_user("iago")
        with self.assert_database_query_count(6):
            result = self.client_get(f"/user_activity/{iago.id}/")
            self.assertEqual(result.status_code, 200)

        with self.assert_database_query_count(8):
            result = self.client_get(f"/activity/plan_ledger/{plan.id}/")
            self.assertEqual(result.status_code, 200)

        with self.assert_database_query_count(7):
            result = self.client_get(f"/activity/remote/logs/server/{server.uuid}/")
            self.assertEqual(result.status_code, 200)

    def test_get_remote_server_guest_and_non_guest_count(self) -> None:
        RemoteRealmAuditLog.objects.bulk_create([RemoteRealmAuditLog(**data) for data in data_list])
        server_id = 1

        # Used in billing code
        remote_server_counts = get_remote_server_guest_and_non_guest_count(
            server_id=server_id, event_time=timezone_now()
        )
        self.assertEqual(remote_server_counts.non_guest_user_count, 73)
        self.assertEqual(remote_server_counts.guest_user_count, 16)

        # Used in remote activity view code
        server_logs = get_remote_server_audit_logs()
        remote_activity_counts = get_remote_customer_user_count(server_logs[server_id])
        self.assertEqual(remote_activity_counts.non_guest_user_count, 73)
        self.assertEqual(remote_activity_counts.guest_user_count, 16)

    def test_remote_activity_with_robust_data(self) -> None:
        def add_plan(customer: Customer, tier: int, fixed_price: bool = False) -> None:
            if fixed_price:
                plan = CustomerPlan.objects.create(
                    customer=customer,
                    billing_cycle_anchor=timezone_now(),
                    billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                    tier=tier,
                    fixed_price=10000,
                    next_invoice_date=add_months(timezone_now(), 12),
                )
            else:
                if tier in (
                    CustomerPlan.TIER_SELF_HOSTED_BASE,
                    CustomerPlan.TIER_SELF_HOSTED_LEGACY,
                    CustomerPlan.TIER_SELF_HOSTED_COMMUNITY,
                ):
                    price_per_license = 0
                else:
                    price_per_license = 1000
                plan = CustomerPlan.objects.create(
                    customer=customer,
                    billing_cycle_anchor=timezone_now(),
                    billing_schedule=CustomerPlan.BILLING_SCHEDULE_ANNUAL,
                    tier=tier,
                    price_per_license=price_per_license,
                    next_invoice_date=add_months(timezone_now(), 12),
                )
            LicenseLedger.objects.create(
                licenses=10,
                licenses_at_next_renewal=10,
                event_time=timezone_now(),
                is_renewal=True,
                plan=plan,
            )

        def add_audit_log_data(
            server: RemoteZulipServer, remote_realm: RemoteRealm | None, realm_id: int | None
        ) -> None:
            extra_data = {
                RemoteRealmAuditLog.ROLE_COUNT: {
                    RemoteRealmAuditLog.ROLE_COUNT_HUMANS: {
                        UserProfile.ROLE_REALM_ADMINISTRATOR: 1,
                        UserProfile.ROLE_REALM_OWNER: 1,
                        UserProfile.ROLE_MODERATOR: 0,
                        UserProfile.ROLE_MEMBER: 0,
                        UserProfile.ROLE_GUEST: 1,
                    }
                }
            }
            if remote_realm is not None:
                RemoteRealmAuditLog.objects.create(
                    server=server,
                    remote_realm=remote_realm,
                    event_type=AuditLogEventType.USER_CREATED,
                    event_time=timezone_now() - timedelta(days=1),
                    extra_data=extra_data,
                )
            else:
                RemoteRealmAuditLog.objects.create(
                    server=server,
                    realm_id=realm_id,
                    event_type=AuditLogEventType.USER_CREATED,
                    event_time=timezone_now() - timedelta(days=1),
                    extra_data=extra_data,
                )

        for i in range(6):
            hostname = f"zulip-{i}.example.com"
            remote_server = RemoteZulipServer.objects.create(
                hostname=hostname, contact_email=f"admin@{hostname}", uuid=uuid.uuid4()
            )
            RemoteZulipServerAuditLog.objects.create(
                event_type=AuditLogEventType.REMOTE_SERVER_CREATED,
                server=remote_server,
                event_time=remote_server.last_updated,
            )
            # We want at least one RemoteZulipServer that has no RemoteRealm
            # as an example of a pre-8.0 release registered remote server.
            if i > 2:
                realm_name = f"realm-name-{i}"
                realm_host = f"realm-host-{i}"
                realm_uuid = uuid.uuid4()
                RemoteRealm.objects.create(
                    server=remote_server,
                    uuid=realm_uuid,
                    host=realm_host,
                    name=realm_name,
                    realm_date_created=datetime(2023, 12, 1, tzinfo=timezone.utc),
                )

        # Remote server on complimentary access plan
        server = RemoteZulipServer.objects.get(hostname="zulip-1.example.com")
        customer = Customer.objects.create(remote_server=server)
        add_plan(customer, tier=CustomerPlan.TIER_SELF_HOSTED_LEGACY)
        add_audit_log_data(server, remote_realm=None, realm_id=2)

        # Remote server paid plan - multiple realms
        server = RemoteZulipServer.objects.get(hostname="zulip-2.example.com")
        customer = Customer.objects.create(remote_server=server)
        add_plan(customer, tier=CustomerPlan.TIER_SELF_HOSTED_BASIC)
        add_audit_log_data(server, remote_realm=None, realm_id=3)
        add_audit_log_data(server, remote_realm=None, realm_id=4)
        add_audit_log_data(server, remote_realm=None, realm_id=5)

        # Single remote realm on remote server - community plan
        realm = RemoteRealm.objects.get(name="realm-name-3")
        customer = Customer.objects.create(remote_realm=realm)
        add_plan(customer, tier=CustomerPlan.TIER_SELF_HOSTED_COMMUNITY)
        add_audit_log_data(realm.server, remote_realm=realm, realm_id=None)

        # Single remote realm on remote server - paid plan
        realm = RemoteRealm.objects.get(name="realm-name-4")
        customer = Customer.objects.create(remote_realm=realm)
        add_plan(customer, tier=CustomerPlan.TIER_SELF_HOSTED_BUSINESS)
        add_audit_log_data(realm.server, remote_realm=realm, realm_id=None)

        # Multiple remote realms on remote server - on different paid plans
        realm = RemoteRealm.objects.get(name="realm-name-5")
        customer = Customer.objects.create(remote_realm=realm)
        add_plan(customer, tier=CustomerPlan.TIER_SELF_HOSTED_BASIC)
        add_audit_log_data(realm.server, remote_realm=realm, realm_id=None)

        remote_server = realm.server
        realm_name = "realm-name-6"
        realm_host = "realm-host-6"
        realm_uuid = uuid.uuid4()
        RemoteRealm.objects.create(
            server=remote_server,
            uuid=realm_uuid,
            host=realm_host,
            name=realm_name,
            realm_date_created=datetime(2023, 12, 1, tzinfo=timezone.utc),
        )

        realm = RemoteRealm.objects.get(name="realm-name-6")
        customer = Customer.objects.create(remote_realm=realm)
        add_plan(customer, tier=CustomerPlan.TIER_SELF_HOSTED_BASIC, fixed_price=True)
        add_audit_log_data(realm.server, remote_realm=realm, realm_id=None)

        self.login("iago")
        with self.assert_database_query_count(11):
            result = self.client_get("/activity/remote")
            self.assertEqual(result.status_code, 200)

        with self.assert_database_query_count(7):
            result = self.client_get(f"/activity/remote/logs/server/{remote_server.uuid}/")
            self.assertEqual(result.status_code, 200)
