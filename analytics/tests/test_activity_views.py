import uuid
from datetime import timedelta
from unittest import mock

from django.utils.timezone import now as timezone_now

from corporate.lib.stripe import add_months
from corporate.models import Customer, CustomerPlan, LicenseLedger
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Client, UserActivity, UserProfile
from zilencer.models import (
    RemoteRealmAuditLog,
    RemoteZulipServer,
    get_remote_server_guest_and_non_guest_count,
)

event_time = timezone_now() - timedelta(days=3)
data_list = [
    {
        "server_id": 1,
        "realm_id": 1,
        "event_type": RemoteRealmAuditLog.USER_CREATED,
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
        "event_type": RemoteRealmAuditLog.USER_ROLE_CHANGED,
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
        "event_type": RemoteRealmAuditLog.USER_CREATED,
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
        "event_type": RemoteRealmAuditLog.USER_CREATED,
        "event_time": event_time,
        "extra_data": {},
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
        RemoteRealmAuditLog.objects.bulk_create([RemoteRealmAuditLog(**data) for data in data_list])
        remote_server = RemoteZulipServer.objects.get(id=1)
        customer = Customer.objects.create(remote_server=remote_server)
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
        RemoteZulipServer.objects.create(
            uuid=str(uuid.uuid4()),
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            contact_email="email@example.com",
        )
        with self.assert_database_query_count(10):
            result = self.client_get("/activity/remote")
            self.assertEqual(result.status_code, 200)

        with self.assert_database_query_count(4):
            result = self.client_get("/activity/integrations")
            self.assertEqual(result.status_code, 200)

        with self.assert_database_query_count(6):
            result = self.client_get("/realm_activity/zulip/")
            self.assertEqual(result.status_code, 200)

        iago = self.example_user("iago")
        with self.assert_database_query_count(5):
            result = self.client_get(f"/user_activity/{iago.id}/")
            self.assertEqual(result.status_code, 200)

    def test_get_remote_server_guest_and_non_guest_count(self) -> None:
        RemoteRealmAuditLog.objects.bulk_create([RemoteRealmAuditLog(**data) for data in data_list])

        remote_server_counts = get_remote_server_guest_and_non_guest_count(
            server_id=1, event_time=timezone_now()
        )
        self.assertEqual(remote_server_counts.non_guest_user_count, 70)
        self.assertEqual(remote_server_counts.guest_user_count, 15)
