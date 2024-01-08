from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional
from unittest import mock

import orjson
import time_machine
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from corporate.lib.stripe import RealmBillingSession, RemoteRealmBillingSession, add_months
from corporate.models import (
    Customer,
    CustomerPlan,
    LicenseLedger,
    SponsoredPlanTypes,
    ZulipSponsorshipRequest,
    get_current_plan_by_customer,
    get_customer_by_realm,
)
from zerver.actions.invites import do_create_multiuse_invite_link
from zerver.actions.realm_settings import do_change_realm_org_type, do_send_realm_reactivation_email
from zerver.actions.user_settings import do_change_user_setting
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import reset_email_visibility_to_everyone_in_zulip_realm
from zerver.models import MultiuseInvite, PreregistrationUser, Realm, UserMessage, UserProfile
from zerver.models.realms import OrgTypeEnum, get_org_type_display_name, get_realm
from zilencer.lib.remote_counts import MissingDataError

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse

import uuid

from zilencer.models import RemoteRealm, RemoteZulipServer, RemoteZulipServerAuditLog


class TestRemoteServerSupportEndpoint(ZulipTestCase):
    @override
    def setUp(self) -> None:
        def add_sponsorship_request(
            name: str, org_type: int, website: str, paid_users: str, plan: str
        ) -> None:
            remote_realm = RemoteRealm.objects.get(name=name)
            customer = Customer.objects.create(remote_realm=remote_realm, sponsorship_pending=True)
            ZulipSponsorshipRequest.objects.create(
                customer=customer,
                org_type=org_type,
                org_website=website,
                org_description="We help people.",
                expected_total_users="20-35",
                paid_users_count=paid_users,
                paid_users_description="",
                requested_plan=plan,
            )

        def add_legacy_plan_and_upgrade(name: str) -> None:
            legacy_anchor = datetime(2050, 1, 1, tzinfo=timezone.utc)
            next_plan_anchor = datetime(2050, 2, 1, tzinfo=timezone.utc)
            billed_licenses = 10
            remote_realm = RemoteRealm.objects.get(name=name)
            billing_session = RemoteRealmBillingSession(remote_realm)

            billing_session.migrate_customer_to_legacy_plan(legacy_anchor, next_plan_anchor)
            customer = billing_session.get_customer()
            assert customer is not None
            legacy_plan = billing_session.get_remote_server_legacy_plan(customer)
            assert legacy_plan is not None
            assert legacy_plan.end_date is not None
            last_ledger_entry = (
                LicenseLedger.objects.filter(plan=legacy_plan).order_by("-id").first()
            )
            assert last_ledger_entry is not None
            last_ledger_entry.licenses_at_next_renewal = billed_licenses
            last_ledger_entry.save(update_fields=["licenses_at_next_renewal"])
            legacy_plan.status = CustomerPlan.SWITCH_PLAN_TIER_AT_PLAN_END
            legacy_plan.save(update_fields=["status"])
            plan_params = {
                "automanage_licenses": True,
                "charge_automatically": False,
                "price_per_license": 100,
                "discount": customer.default_discount,
                "billing_cycle_anchor": next_plan_anchor,
                "billing_schedule": CustomerPlan.BILLING_SCHEDULE_MONTHLY,
                "tier": CustomerPlan.TIER_SELF_HOSTED_BASIC,
                "status": CustomerPlan.NEVER_STARTED,
            }
            CustomerPlan.objects.create(
                customer=customer, next_invoice_date=next_plan_anchor, **plan_params
            )

        super().setUp()

        # Set up some initial example data.
        for i in range(5):
            hostname = f"zulip-{i}.example.com"
            remote_server = RemoteZulipServer.objects.create(
                hostname=hostname, contact_email=f"admin@{hostname}", uuid=uuid.uuid4()
            )
            RemoteZulipServerAuditLog.objects.create(
                event_type=RemoteZulipServerAuditLog.REMOTE_SERVER_CREATED,
                server=remote_server,
                event_time=remote_server.last_updated,
            )
            # We want at least one RemoteZulipServer that has no RemoteRealm
            # as an example of a pre-8.0 release registered remote server.
            if i > 1:
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

        # Add a deactivated server, which should be excluded from search results.
        server = RemoteZulipServer.objects.get(hostname="zulip-0.example.com")
        server.deactivated = True
        server.save(update_fields=["deactivated"])

        # Add example sponsorship request data
        add_sponsorship_request(
            name="realm-name-2",
            org_type=OrgTypeEnum.Community.value,
            website="",
            paid_users="None",
            plan=SponsoredPlanTypes.BUSINESS.value,
        )

        add_sponsorship_request(
            name="realm-name-3",
            org_type=OrgTypeEnum.OpenSource.value,
            website="example.org",
            paid_users="",
            plan=SponsoredPlanTypes.COMMUNITY.value,
        )

        # Add expected legacy customer and plan data
        add_legacy_plan_and_upgrade(name="realm-name-4")

    def test_search(self) -> None:
        def assert_server_details_in_response(
            html_response: "TestHttpResponse", hostname: str
        ) -> None:
            self.assert_in_success_response(
                [
                    f"<h3>{hostname} <a",
                    f"<b>Contact email</b>: admin@{hostname}",
                    "<b>Date created</b>:",
                    "<b>UUID</b>:",
                    "<b>Zulip version</b>:",
                    "<b>Plan type</b>: Self-managed<br />",
                    "<b>Non-guest user count</b>: 0<br />",
                    "<b>Guest user count</b>: 0<br />",
                ],
                html_response,
            )
            self.assert_not_in_success_response(["<h3>zulip-0.example.com"], result)

        def assert_realm_details_in_response(
            html_response: "TestHttpResponse", name: str, host: str
        ) -> None:
            self.assert_in_success_response(
                [
                    f"<h3>{name}</h3>",
                    f"<b>Remote realm host:</b> {host}<br />",
                    "<b>Date created</b>: 01 December 2023",
                    "<b>Org type</b>: Unspecified<br />",
                    "<b>Has remote realms</b>: True<br />",
                ],
                html_response,
            )
            self.assert_not_in_success_response(["<h3>zulip-1.example.com"], result)

        def check_remote_server_with_no_realms(result: "TestHttpResponse") -> None:
            assert_server_details_in_response(result, "zulip-1.example.com")
            self.assert_not_in_success_response(
                ["<h3>zulip-2.example.com", "<b>Remote realm host:</b>"], result
            )
            self.assert_in_success_response(["<b>Has remote realms</b>: False<br />"], result)

        def check_sponsorship_request_no_website(result: "TestHttpResponse") -> None:
            self.assert_in_success_response(
                [
                    "<li><b>Organization type</b>: Community</li>",
                    "<li><b>Organization website</b>: No website submitted</li>",
                    "<li><b>Paid staff</b>: None</li>",
                    "<li><b>Requested plan</b>: Business</li>",
                    "<li><b>Organization description</b>: We help people.</li>",
                    "<li><b>Estimated total users</b>: 20-35</li>",
                    "<li><b>Description of paid staff</b>: </li>",
                ],
                result,
            )

        def check_sponsorship_request_with_website(result: "TestHttpResponse") -> None:
            self.assert_in_success_response(
                [
                    "<li><b>Organization type</b>: Open-source project</li>",
                    "<li><b>Organization website</b>: example.org</li>",
                    "<li><b>Paid staff</b>: </li>",
                    "<li><b>Requested plan</b>: Community</li>",
                    "<li><b>Organization description</b>: We help people.</li>",
                    "<li><b>Estimated total users</b>: 20-35</li>",
                    "<li><b>Description of paid staff</b>: </li>",
                ],
                result,
            )

        def check_no_sponsorship_request(result: "TestHttpResponse") -> None:
            self.assert_not_in_success_response(
                [
                    "<li><b>Organization description</b>: We help people.</li>",
                    "<li><b>Estimated total users</b>: 20-35</li>",
                    "<li><b>Description of paid staff</b>: </li>",
                ],
                result,
            )

        def check_legacy_and_next_plan(result: "TestHttpResponse") -> None:
            self.assert_in_success_response(
                [
                    "<h4>📅 Current plan information:</h4>",
                    "<b>Plan name</b>: Self-managed (legacy plan)<br />",
                    "<b>Status</b>: New plan scheduled<br />",
                    "<b>End date</b>: 01 February 2050<br />",
                    "<h4>⏱️ Next plan information:</h4>",
                    "<b>Plan name</b>: Zulip Basic<br />",
                    "<b>Status</b>: Never started<br />",
                    "<b>Start date</b>: 01 February 2050<br />",
                    "<b>Billing schedule</b>: Monthly<br />",
                    "<b>Price per license</b>: $1.00<br />",
                    "<b>Estimated billed licenses</b>: 10<br />",
                    "<b>Estimated annual revenue</b>: $120.00<br />",
                ],
                result,
            )

        self.login("cordelia")

        result = self.client_get("/activity/remote/support")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        # Iago is the user with the appropriate permissions to access this page.
        self.login("iago")
        assert self.example_user("iago").is_staff

        result = self.client_get("/activity/remote/support")
        self.assert_in_success_response(
            [
                'input type="text" name="q" class="input-xxlarge search-query" placeholder="hostname or contact email"'
            ],
            result,
        )

        server = 0
        result = self.client_get("/activity/remote/support", {"q": "example.com"})
        self.assert_not_in_success_response([f"<h3>zulip-{server}.example.com"], result)
        for i in range(5):
            if i != server:
                self.assert_in_success_response([f"<h3>zulip-{i}.example.com <a"], result)

        server = 1
        result = self.client_get("/activity/remote/support", {"q": f"zulip-{server}.example.com"})
        check_remote_server_with_no_realms(result)

        server = 2
        with mock.patch("analytics.views.support.compute_max_monthly_messages", return_value=1000):
            result = self.client_get(
                "/activity/remote/support", {"q": f"zulip-{server}.example.com"}
            )
        self.assert_in_success_response(["<b>Max monthly messages</b>: 1000"], result)
        assert_server_details_in_response(result, f"zulip-{server}.example.com")
        assert_realm_details_in_response(result, f"realm-name-{server}", f"realm-host-{server}")
        check_sponsorship_request_no_website(result)

        with mock.patch(
            "analytics.views.support.compute_max_monthly_messages", side_effect=MissingDataError
        ):
            result = self.client_get(
                "/activity/remote/support", {"q": f"zulip-{server}.example.com"}
            )
        self.assert_in_success_response(
            ["<b>Max monthly messages</b>: Recent analytics data missing"], result
        )
        assert_server_details_in_response(result, f"zulip-{server}.example.com")
        assert_realm_details_in_response(result, f"realm-name-{server}", f"realm-host-{server}")
        check_sponsorship_request_no_website(result)

        server = 3
        result = self.client_get("/activity/remote/support", {"q": f"zulip-{server}.example.com"})
        assert_server_details_in_response(result, f"zulip-{server}.example.com")
        assert_realm_details_in_response(result, f"realm-name-{server}", f"realm-host-{server}")
        check_sponsorship_request_with_website(result)

        server = 4
        result = self.client_get("/activity/remote/support", {"q": f"zulip-{server}.example.com"})
        assert_server_details_in_response(result, f"zulip-{server}.example.com")
        assert_realm_details_in_response(result, f"realm-name-{server}", f"realm-host-{server}")
        check_no_sponsorship_request(result)
        check_legacy_and_next_plan(result)


class TestSupportEndpoint(ZulipTestCase):
    def create_customer_and_plan(self, realm: Realm, monthly: bool = False) -> Customer:
        now = datetime(2016, 1, 2, tzinfo=timezone.utc)
        billing_schedule = CustomerPlan.BILLING_SCHEDULE_ANNUAL
        price_per_license = 8000
        months = 12

        if monthly:
            billing_schedule = CustomerPlan.BILLING_SCHEDULE_MONTHLY
            price_per_license = 800
            months = 1

        customer = Customer.objects.create(realm=realm)
        plan = CustomerPlan.objects.create(
            customer=customer,
            billing_cycle_anchor=now,
            billing_schedule=billing_schedule,
            tier=CustomerPlan.TIER_CLOUD_STANDARD,
            price_per_license=price_per_license,
            next_invoice_date=add_months(now, months),
        )
        LicenseLedger.objects.create(
            licenses=10,
            licenses_at_next_renewal=10,
            event_time=timezone_now(),
            is_renewal=True,
            plan=plan,
        )
        return customer

    def test_search(self) -> None:
        reset_email_visibility_to_everyone_in_zulip_realm()
        lear_user = self.lear_user("king")
        lear_user.is_staff = True
        lear_user.save(update_fields=["is_staff"])
        lear_realm = get_realm("lear")

        def assert_user_details_in_html_response(
            html_response: "TestHttpResponse", full_name: str, email: str, role: str
        ) -> None:
            self.assert_in_success_response(
                [
                    '<span class="label">user</span>\n',
                    f"<h3>{full_name}</h3>",
                    f"<b>Email</b>: {email}",
                    "<b>Is active</b>: True<br />",
                    f"<b>Role</b>: {role}<br />",
                ],
                html_response,
            )

        def create_invitation(
            stream: str, invitee_email: str, realm: Optional[Realm] = None
        ) -> None:
            invite_expires_in_minutes = 10 * 24 * 60
            self.client_post(
                "/json/invites",
                {
                    "invitee_emails": [invitee_email],
                    "stream_ids": orjson.dumps([self.get_stream_id(stream, realm)]).decode(),
                    "invite_expires_in_minutes": invite_expires_in_minutes,
                    "invite_as": PreregistrationUser.INVITE_AS["MEMBER"],
                },
                subdomain=realm.string_id if realm is not None else "zulip",
            )

        def check_hamlet_user_query_result(result: "TestHttpResponse") -> None:
            assert_user_details_in_html_response(
                result, "King Hamlet", self.example_email("hamlet"), "Member"
            )
            self.assert_in_success_response(
                [
                    f"<b>Admins</b>: {self.example_email('iago')}\n",
                    f"<b>Owners</b>: {self.example_email('desdemona')}\n",
                    'class="copy-button" data-copytext="{}">'.format(self.example_email("iago")),
                    'class="copy-button" data-copytext="{}">'.format(
                        self.example_email("desdemona")
                    ),
                ],
                result,
            )

        def check_lear_user_query_result(result: "TestHttpResponse") -> None:
            assert_user_details_in_html_response(
                result, lear_user.full_name, lear_user.email, "Member"
            )

        def check_othello_user_query_result(result: "TestHttpResponse") -> None:
            assert_user_details_in_html_response(
                result, "Othello, the Moor of Venice", self.example_email("othello"), "Member"
            )

        def check_polonius_user_query_result(result: "TestHttpResponse") -> None:
            assert_user_details_in_html_response(
                result, "Polonius", self.example_email("polonius"), "Guest"
            )

        def check_zulip_realm_query_result(result: "TestHttpResponse") -> None:
            zulip_realm = get_realm("zulip")
            first_human_user = zulip_realm.get_first_human_user()
            assert first_human_user is not None
            self.assert_in_success_response(
                [
                    f"<b>First human user</b>: {first_human_user.delivery_email}\n",
                    f'<input type="hidden" name="realm_id" value="{zulip_realm.id}"',
                    "Zulip Dev</h3>",
                    '<option value="1" selected>Self-hosted</option>',
                    '<option value="2" >Limited</option>',
                    'input type="number" name="discount" value="None"',
                    '<option value="active" selected>Active</option>',
                    '<option value="deactivated" >Deactivated</option>',
                    f'<option value="{zulip_realm.org_type}" selected>',
                    'scrub-realm-button">',
                    'data-string-id="zulip"',
                ],
                result,
            )

        def check_lear_realm_query_result(result: "TestHttpResponse") -> None:
            self.assert_in_success_response(
                [
                    f'<input type="hidden" name="realm_id" value="{lear_realm.id}"',
                    "Lear &amp; Co.</h3>",
                    '<option value="1" selected>Self-hosted</option>',
                    '<option value="2" >Limited</option>',
                    'input type="number" name="discount" value="None"',
                    '<option value="active" selected>Active</option>',
                    '<option value="deactivated" >Deactivated</option>',
                    'scrub-realm-button">',
                    'data-string-id="lear"',
                    "<b>Plan name</b>: Zulip Cloud Standard",
                    "<b>Status</b>: Active",
                    "<b>Billing schedule</b>: Annual",
                    "<b>Licenses</b>: 2/10 (Manual)",
                    "<b>Price per license</b>: $80.00",
                    "<b>Annual recurring revenue</b>: $800.00",
                    "<b>Next invoice date</b>: 02 January 2017",
                    '<option value="send_invoice" selected>',
                    '<option value="charge_automatically" >',
                ],
                result,
            )

        def check_preregistration_user_query_result(
            result: "TestHttpResponse", email: str, invite: bool = False
        ) -> None:
            self.assert_in_success_response(
                [
                    '<span class="label">preregistration user</span>\n',
                    f"<b>Email</b>: {email}",
                ],
                result,
            )
            if invite:
                self.assert_in_success_response(['<span class="label">invite</span>'], result)
                self.assert_in_success_response(
                    [
                        "<b>Expires in</b>: 1\xa0week, 3\xa0days",
                        "<b>Status</b>: Link has not been used",
                    ],
                    result,
                )
                self.assert_in_success_response([], result)
            else:
                self.assert_not_in_success_response(['<span class="label">invite</span>'], result)
                self.assert_in_success_response(
                    [
                        "<b>Expires in</b>: 1\xa0day",
                        "<b>Status</b>: Link has not been used",
                    ],
                    result,
                )

        def check_realm_creation_query_result(result: "TestHttpResponse", email: str) -> None:
            self.assert_in_success_response(
                [
                    '<span class="label">preregistration user</span>\n',
                    '<span class="label">realm creation</span>\n',
                    "<b>Link</b>: http://testserver/accounts/do_confirm/",
                    "<b>Expires in</b>: 1\xa0day",
                ],
                result,
            )

        def check_multiuse_invite_link_query_result(result: "TestHttpResponse") -> None:
            self.assert_in_success_response(
                [
                    '<span class="label">multiuse invite</span>\n',
                    "<b>Link</b>: http://zulip.testserver/join/",
                    "<b>Expires in</b>: 1\xa0week, 3\xa0days",
                ],
                result,
            )

        def check_realm_reactivation_link_query_result(result: "TestHttpResponse") -> None:
            self.assert_in_success_response(
                [
                    '<span class="label">realm reactivation</span>\n',
                    "<b>Link</b>: http://zulip.testserver/reactivate/",
                    "<b>Expires in</b>: 1\xa0day",
                ],
                result,
            )

        def get_check_query_result(
            query: str, count: int, subdomain: str = "zulip"
        ) -> "TestHttpResponse":
            result = self.client_get("/activity/support", {"q": query}, subdomain=subdomain)
            self.assertEqual(result.content.decode().count("support-query-result"), count)
            return result

        self.login("cordelia")

        result = self.client_get("/activity/support")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        self.login("iago")

        do_change_user_setting(
            self.example_user("hamlet"),
            "email_address_visibility",
            UserProfile.EMAIL_ADDRESS_VISIBILITY_NOBODY,
            acting_user=None,
        )

        self.create_customer_and_plan(lear_realm)

        result = self.client_get("/activity/support")
        self.assert_in_success_response(
            ['<input type="text" name="q" class="input-xxlarge search-query"'], result
        )

        result = get_check_query_result(self.example_email("hamlet"), 1)
        check_hamlet_user_query_result(result)
        check_zulip_realm_query_result(result)

        # Search should be case-insensitive:
        assert self.example_email("hamlet") != self.example_email("hamlet").upper()
        result = get_check_query_result(self.example_email("hamlet").upper(), 1)
        check_hamlet_user_query_result(result)
        check_zulip_realm_query_result(result)

        result = get_check_query_result(lear_user.email, 1)
        check_lear_user_query_result(result)
        check_lear_realm_query_result(result)

        result = get_check_query_result(self.example_email("polonius"), 1)
        check_polonius_user_query_result(result)
        check_zulip_realm_query_result(result)

        result = get_check_query_result("lear", 1)
        check_lear_realm_query_result(result)

        result = get_check_query_result("http://lear.testserver", 1)
        check_lear_realm_query_result(result)

        with self.settings(REALM_HOSTS={"zulip": "localhost"}):
            result = get_check_query_result("http://localhost", 1)
            check_zulip_realm_query_result(result)

        result = get_check_query_result("hamlet@zulip.com, lear", 2)
        check_hamlet_user_query_result(result)
        check_zulip_realm_query_result(result)
        check_lear_realm_query_result(result)

        result = get_check_query_result("King hamlet,lear", 2)
        check_hamlet_user_query_result(result)
        check_zulip_realm_query_result(result)
        check_lear_realm_query_result(result)

        result = get_check_query_result("Othello, the Moor of Venice", 1)
        check_othello_user_query_result(result)
        check_zulip_realm_query_result(result)

        result = get_check_query_result("lear, Hamlet <hamlet@zulip.com>", 2)
        check_hamlet_user_query_result(result)
        check_zulip_realm_query_result(result)
        check_lear_realm_query_result(result)

        self.client_post("/accounts/home/", {"email": self.nonreg_email("test")})
        self.login("iago")

        def query_result_from_before(*args: Any) -> "TestHttpResponse":
            with time_machine.travel((timezone_now() - timedelta(minutes=50)), tick=False):
                return get_check_query_result(*args)

        result = query_result_from_before(self.nonreg_email("test"), 1)
        check_preregistration_user_query_result(result, self.nonreg_email("test"))
        check_zulip_realm_query_result(result)

        create_invitation("Denmark", self.nonreg_email("test1"))
        result = query_result_from_before(self.nonreg_email("test1"), 1)
        check_preregistration_user_query_result(result, self.nonreg_email("test1"), invite=True)
        check_zulip_realm_query_result(result)

        email = self.nonreg_email("alice")
        self.submit_realm_creation_form(
            email, realm_subdomain="custom-test", realm_name="Zulip test"
        )
        result = query_result_from_before(email, 1)
        check_realm_creation_query_result(result, email)

        invite_expires_in_minutes = 10 * 24 * 60
        do_create_multiuse_invite_link(
            self.example_user("hamlet"),
            invited_as=1,
            invite_expires_in_minutes=invite_expires_in_minutes,
        )
        result = query_result_from_before("zulip", 2)
        check_multiuse_invite_link_query_result(result)
        check_zulip_realm_query_result(result)
        MultiuseInvite.objects.all().delete()

        do_send_realm_reactivation_email(get_realm("zulip"), acting_user=None)
        result = query_result_from_before("zulip", 2)
        check_realm_reactivation_link_query_result(result)
        check_zulip_realm_query_result(result)

        lear_nonreg_email = "newguy@lear.org"
        self.client_post("/accounts/home/", {"email": lear_nonreg_email}, subdomain="lear")
        result = query_result_from_before(lear_nonreg_email, 1)
        check_preregistration_user_query_result(result, lear_nonreg_email)
        check_lear_realm_query_result(result)

        self.login_user(lear_user)
        create_invitation("general", "newguy2@lear.org", lear_realm)
        result = query_result_from_before("newguy2@lear.org", 1, lear_realm.string_id)
        check_preregistration_user_query_result(result, "newguy2@lear.org", invite=True)
        check_lear_realm_query_result(result)

    def test_get_org_type_display_name(self) -> None:
        self.assertEqual(get_org_type_display_name(Realm.ORG_TYPES["business"]["id"]), "Business")
        self.assertEqual(get_org_type_display_name(883), "")

    def test_unspecified_org_type_correctly_displayed(self) -> None:
        """
        Unspecified org type is special in that it is marked to not be shown
        on the registration page (because organitions are not meant to be able to choose it),
        but should be correctly shown at the /support/ endpoint.
        """
        realm = get_realm("zulip")

        do_change_realm_org_type(realm, 0, acting_user=None)
        self.assertEqual(realm.org_type, 0)

        self.login("iago")

        result = self.client_get("/activity/support", {"q": "zulip"}, subdomain="zulip")
        self.assert_in_success_response(
            [
                f'<input type="hidden" name="realm_id" value="{realm.id}"',
                '<option value="0" selected>',
            ],
            result,
        )

    def test_change_billing_modality(self) -> None:
        realm = get_realm("zulip")
        customer = self.create_customer_and_plan(realm)

        cordelia = self.example_user("cordelia")
        self.login_user(cordelia)
        result = self.client_post(
            "/activity/support",
            {"realm_id": f"{realm.id}", "billing_method": "charge_automatically"},
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        iago = self.example_user("iago")
        self.login_user(iago)

        result = self.client_post(
            "/activity/support",
            {"realm_id": f"{realm.id}", "billing_modality": "charge_automatically"},
        )
        self.assert_in_success_response(
            ["Billing collection method of zulip updated to charge automatically"], result
        )
        plan = get_current_plan_by_customer(customer)
        assert plan is not None
        self.assertEqual(plan.charge_automatically, True)

        result = self.client_post(
            "/activity/support", {"realm_id": f"{realm.id}", "billing_modality": "send_invoice"}
        )
        self.assert_in_success_response(
            ["Billing collection method of zulip updated to send invoice"], result
        )
        plan.refresh_from_db()
        self.assertEqual(plan.charge_automatically, False)

    def test_change_realm_plan_type(self) -> None:
        cordelia = self.example_user("cordelia")
        self.login_user(cordelia)

        result = self.client_post(
            "/activity/support", {"realm_id": f"{cordelia.realm_id}", "plan_type": "2"}
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        iago = self.example_user("iago")
        self.login_user(iago)

        with mock.patch("analytics.views.support.do_change_realm_plan_type") as m:
            result = self.client_post(
                "/activity/support", {"realm_id": f"{iago.realm_id}", "plan_type": "2"}
            )
            m.assert_called_once_with(get_realm("zulip"), 2, acting_user=iago)
            self.assert_in_success_response(
                ["Plan type of zulip changed from Self-hosted to Limited"], result
            )

        with mock.patch("analytics.views.support.do_change_realm_plan_type") as m:
            result = self.client_post(
                "/activity/support", {"realm_id": f"{iago.realm_id}", "plan_type": "10"}
            )
            m.assert_called_once_with(get_realm("zulip"), 10, acting_user=iago)
            self.assert_in_success_response(
                ["Plan type of zulip changed from Self-hosted to Plus"], result
            )

    def test_change_org_type(self) -> None:
        cordelia = self.example_user("cordelia")
        self.login_user(cordelia)

        result = self.client_post(
            "/activity/support", {"realm_id": f"{cordelia.realm_id}", "org_type": "70"}
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        iago = self.example_user("iago")
        self.login_user(iago)

        with mock.patch("analytics.views.support.do_change_realm_org_type") as m:
            result = self.client_post(
                "/activity/support", {"realm_id": f"{iago.realm_id}", "org_type": "70"}
            )
            m.assert_called_once_with(get_realm("zulip"), 70, acting_user=iago)
            self.assert_in_success_response(
                ["Org type of zulip changed from Business to Government"], result
            )

    def test_attach_discount(self) -> None:
        lear_realm = get_realm("lear")
        customer = self.create_customer_and_plan(lear_realm, True)

        cordelia = self.example_user("cordelia")
        self.login_user(cordelia)
        result = self.client_post(
            "/activity/support", {"realm_id": f"{lear_realm.id}", "discount": "25"}
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        iago = self.example_user("iago")
        self.login_user(iago)

        result = self.client_post(
            "/activity/support", {"realm_id": f"{lear_realm.id}", "discount": "25"}
        )
        self.assert_in_success_response(["Discount for lear changed to 25% from 0%"], result)

        customer.refresh_from_db()
        plan = get_current_plan_by_customer(customer)
        assert plan is not None
        self.assertEqual(customer.default_discount, Decimal(25))
        self.assertEqual(plan.discount, Decimal(25))

        result = self.client_get("/activity/support", {"q": "lear"})
        self.assert_in_success_response(
            [
                "<b>Plan name</b>: Zulip Cloud Standard",
                "<b>Status</b>: Active",
                "<b>Discount</b>: 25%",
                "<b>Billing schedule</b>: Monthly",
                "<b>Licenses</b>: 2/10 (Manual)",
                "<b>Price per license</b>: $6.00",
                "<b>Annual recurring revenue</b>: $720.00",
                "<b>Next invoice date</b>: 02 February 2016",
            ],
            result,
        )

    def test_change_sponsorship_status(self) -> None:
        lear_realm = get_realm("lear")
        self.assertIsNone(get_customer_by_realm(lear_realm))

        cordelia = self.example_user("cordelia")
        self.login_user(cordelia)

        result = self.client_post(
            "/activity/support", {"realm_id": f"{lear_realm.id}", "sponsorship_pending": "true"}
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        iago = self.example_user("iago")
        self.login_user(iago)

        result = self.client_post(
            "/activity/support", {"realm_id": f"{lear_realm.id}", "sponsorship_pending": "true"}
        )
        self.assert_in_success_response(["lear marked as pending sponsorship."], result)
        customer = get_customer_by_realm(lear_realm)
        assert customer is not None
        self.assertTrue(customer.sponsorship_pending)

        result = self.client_post(
            "/activity/support", {"realm_id": f"{lear_realm.id}", "sponsorship_pending": "false"}
        )
        self.assert_in_success_response(["lear is no longer pending sponsorship."], result)
        customer = get_customer_by_realm(lear_realm)
        assert customer is not None
        self.assertFalse(customer.sponsorship_pending)

    def test_approve_sponsorship(self) -> None:
        support_admin = self.example_user("iago")
        lear_realm = get_realm("lear")
        billing_session = RealmBillingSession(
            user=support_admin, realm=lear_realm, support_session=True
        )
        billing_session.update_customer_sponsorship_status(True)
        king_user = self.lear_user("king")
        king_user.role = UserProfile.ROLE_REALM_OWNER
        king_user.save()

        cordelia = self.example_user("cordelia")
        self.login_user(cordelia)

        result = self.client_post(
            "/activity/support",
            {"realm_id": f"{lear_realm.id}", "approve_sponsorship": "true"},
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        iago = self.example_user("iago")
        self.login_user(iago)

        result = self.client_post(
            "/activity/support",
            {"realm_id": f"{lear_realm.id}", "approve_sponsorship": "true"},
        )
        self.assert_in_success_response(["Sponsorship approved for lear"], result)
        lear_realm.refresh_from_db()
        self.assertEqual(lear_realm.plan_type, Realm.PLAN_TYPE_STANDARD_FREE)
        customer = get_customer_by_realm(lear_realm)
        assert customer is not None
        self.assertFalse(customer.sponsorship_pending)
        messages = UserMessage.objects.filter(user_profile=king_user)
        self.assertIn(
            "request for sponsored hosting has been approved", messages[0].message.content
        )
        self.assert_length(messages, 1)

    def test_activate_or_deactivate_realm(self) -> None:
        cordelia = self.example_user("cordelia")
        lear_realm = get_realm("lear")
        self.login_user(cordelia)

        result = self.client_post(
            "/activity/support", {"realm_id": f"{lear_realm.id}", "status": "deactivated"}
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        self.login("iago")

        with mock.patch("analytics.views.support.do_deactivate_realm") as m:
            result = self.client_post(
                "/activity/support", {"realm_id": f"{lear_realm.id}", "status": "deactivated"}
            )
            m.assert_called_once_with(lear_realm, acting_user=self.example_user("iago"))
            self.assert_in_success_response(["lear deactivated"], result)

        with mock.patch("analytics.views.support.do_send_realm_reactivation_email") as m:
            result = self.client_post(
                "/activity/support", {"realm_id": f"{lear_realm.id}", "status": "active"}
            )
            m.assert_called_once_with(lear_realm, acting_user=self.example_user("iago"))
            self.assert_in_success_response(
                ["Realm reactivation email sent to admins of lear"], result
            )

    def test_change_subdomain(self) -> None:
        cordelia = self.example_user("cordelia")
        lear_realm = get_realm("lear")
        self.login_user(cordelia)

        result = self.client_post(
            "/activity/support", {"realm_id": f"{lear_realm.id}", "new_subdomain": "new_name"}
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")
        self.login("iago")

        result = self.client_post(
            "/activity/support", {"realm_id": f"{lear_realm.id}", "new_subdomain": "new-name"}
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/activity/support?q=new-name")
        realm_id = lear_realm.id
        lear_realm = get_realm("new-name")
        self.assertEqual(lear_realm.id, realm_id)
        self.assertTrue(Realm.objects.filter(string_id="lear").exists())
        self.assertTrue(Realm.objects.filter(string_id="lear")[0].deactivated)

        result = self.client_post(
            "/activity/support", {"realm_id": f"{lear_realm.id}", "new_subdomain": "new-name"}
        )
        self.assert_in_success_response(
            ["Subdomain already in use. Please choose a different one."], result
        )

        result = self.client_post(
            "/activity/support", {"realm_id": f"{lear_realm.id}", "new_subdomain": "zulip"}
        )
        self.assert_in_success_response(
            ["Subdomain already in use. Please choose a different one."], result
        )

        result = self.client_post(
            "/activity/support", {"realm_id": f"{lear_realm.id}", "new_subdomain": "lear"}
        )
        self.assert_in_success_response(
            ["Subdomain already in use. Please choose a different one."], result
        )

        # Test renaming to a "reserved" subdomain
        result = self.client_post(
            "/activity/support", {"realm_id": f"{lear_realm.id}", "new_subdomain": "your-org"}
        )
        self.assert_in_success_response(
            ["Subdomain reserved. Please choose a different one."], result
        )

    def test_modify_plan_for_downgrade_at_end_of_billing_cycle(self) -> None:
        realm = get_realm("zulip")
        customer = self.create_customer_and_plan(realm)

        cordelia = self.example_user("cordelia")
        self.login_user(cordelia)
        result = self.client_post(
            "/activity/support",
            {"realm_id": f"{realm.id}", "modify_plan": "downgrade_at_billing_cycle_end"},
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        iago = self.example_user("iago")
        self.login_user(iago)

        with self.assertLogs("corporate.stripe", "INFO") as m:
            result = self.client_post(
                "/activity/support",
                {
                    "realm_id": f"{realm.id}",
                    "modify_plan": "downgrade_at_billing_cycle_end",
                },
            )
            self.assert_in_success_response(
                ["zulip marked for downgrade at the end of billing cycle"], result
            )
            customer.refresh_from_db()
            plan = get_current_plan_by_customer(customer)
            assert plan is not None
            self.assertEqual(plan.status, CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE)
            expected_log = f"INFO:corporate.stripe:Change plan status: Customer.id: {customer.id}, CustomerPlan.id: {plan.id}, status: {CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE}"
            self.assertEqual(m.output[0], expected_log)

    def test_modify_plan_for_downgrade_now_without_additional_licenses(self) -> None:
        realm = get_realm("zulip")
        customer = self.create_customer_and_plan(realm)
        plan = get_current_plan_by_customer(customer)
        assert plan is not None

        cordelia = self.example_user("cordelia")
        self.login_user(cordelia)
        result = self.client_post(
            "/activity/support",
            {"realm_id": f"{realm.id}", "modify_plan": "downgrade_now_without_additional_licenses"},
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        iago = self.example_user("iago")
        self.login_user(iago)

        result = self.client_post(
            "/activity/support",
            {
                "realm_id": f"{iago.realm_id}",
                "modify_plan": "downgrade_now_without_additional_licenses",
            },
        )
        self.assert_in_success_response(
            ["zulip downgraded without creating additional invoices"], result
        )

        plan.refresh_from_db()
        self.assertEqual(plan.status, CustomerPlan.ENDED)
        realm.refresh_from_db()
        self.assertEqual(realm.plan_type, Realm.PLAN_TYPE_LIMITED)

    def test_scrub_realm(self) -> None:
        cordelia = self.example_user("cordelia")
        lear_realm = get_realm("lear")
        self.login_user(cordelia)

        result = self.client_post(
            "/activity/support", {"realm_id": f"{lear_realm.id}", "discount": "25"}
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        self.login("iago")

        with mock.patch("analytics.views.support.do_scrub_realm") as m:
            result = self.client_post(
                "/activity/support", {"realm_id": f"{lear_realm.id}", "scrub_realm": "true"}
            )
            m.assert_called_once_with(lear_realm, acting_user=self.example_user("iago"))
            self.assert_in_success_response(["lear scrubbed"], result)

        with mock.patch("analytics.views.support.do_scrub_realm") as m:
            result = self.client_post("/activity/support", {"realm_id": f"{lear_realm.id}"})
            self.assert_json_error(result, "Invalid parameters")
            m.assert_not_called()

    def test_delete_user(self) -> None:
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        hamlet_email = hamlet.delivery_email
        realm = get_realm("zulip")
        self.login_user(cordelia)

        result = self.client_post(
            "/activity/support", {"realm_id": f"{realm.id}", "delete_user_by_id": hamlet.id}
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        self.login("iago")

        with mock.patch("analytics.views.support.do_delete_user_preserving_messages") as m:
            result = self.client_post(
                "/activity/support",
                {"realm_id": f"{realm.id}", "delete_user_by_id": hamlet.id},
            )
            m.assert_called_once_with(hamlet)
            self.assert_in_success_response([f"{hamlet_email} in zulip deleted"], result)
