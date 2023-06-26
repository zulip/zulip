from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional
from unittest import mock

import orjson
from django.utils.timezone import now as timezone_now

from corporate.lib.stripe import add_months, update_sponsorship_status
from corporate.models import Customer, CustomerPlan, LicenseLedger, get_customer_by_realm
from zerver.actions.invites import do_create_multiuse_invite_link
from zerver.actions.realm_settings import do_change_realm_org_type, do_send_realm_reactivation_email
from zerver.actions.user_settings import do_change_user_setting
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import reset_email_visibility_to_everyone_in_zulip_realm
from zerver.models import (
    MultiuseInvite,
    PreregistrationUser,
    Realm,
    UserMessage,
    UserProfile,
    get_org_type_display_name,
    get_realm,
)

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class TestSupportEndpoint(ZulipTestCase):
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
                    "<b>Name</b>: Zulip Cloud Standard",
                    "<b>Status</b>: Active",
                    "<b>Billing schedule</b>: Annual",
                    "<b>Licenses</b>: 2/10 (Manual)",
                    "<b>Price per license</b>: $80.0",
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

        customer = Customer.objects.create(realm=lear_realm, stripe_customer_id="cus_123")
        now = datetime(2016, 1, 2, tzinfo=timezone.utc)
        plan = CustomerPlan.objects.create(
            customer=customer,
            billing_cycle_anchor=now,
            billing_schedule=CustomerPlan.ANNUAL,
            tier=CustomerPlan.STANDARD,
            price_per_license=8000,
            next_invoice_date=add_months(now, 12),
        )
        LicenseLedger.objects.create(
            licenses=10,
            licenses_at_next_renewal=10,
            event_time=timezone_now(),
            is_renewal=True,
            plan=plan,
        )

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

        with mock.patch(
            "analytics.views.support.timezone_now",
            return_value=timezone_now() - timedelta(minutes=50),
        ):
            self.client_post("/accounts/home/", {"email": self.nonreg_email("test")})
            self.login("iago")
            result = get_check_query_result(self.nonreg_email("test"), 1)
            check_preregistration_user_query_result(result, self.nonreg_email("test"))
            check_zulip_realm_query_result(result)

            create_invitation("Denmark", self.nonreg_email("test1"))
            result = get_check_query_result(self.nonreg_email("test1"), 1)
            check_preregistration_user_query_result(result, self.nonreg_email("test1"), invite=True)
            check_zulip_realm_query_result(result)

            email = self.nonreg_email("alice")
            self.submit_realm_creation_form(
                email, realm_subdomain="custom-test", realm_name="Zulip test"
            )
            result = get_check_query_result(email, 1)
            check_realm_creation_query_result(result, email)

            invite_expires_in_minutes = 10 * 24 * 60
            do_create_multiuse_invite_link(
                self.example_user("hamlet"),
                invited_as=1,
                invite_expires_in_minutes=invite_expires_in_minutes,
            )
            result = get_check_query_result("zulip", 2)
            check_multiuse_invite_link_query_result(result)
            check_zulip_realm_query_result(result)
            MultiuseInvite.objects.all().delete()

            do_send_realm_reactivation_email(get_realm("zulip"), acting_user=None)
            result = get_check_query_result("zulip", 2)
            check_realm_reactivation_link_query_result(result)
            check_zulip_realm_query_result(result)

            lear_nonreg_email = "newguy@lear.org"
            self.client_post("/accounts/home/", {"email": lear_nonreg_email}, subdomain="lear")
            result = get_check_query_result(lear_nonreg_email, 1)
            check_preregistration_user_query_result(result, lear_nonreg_email)
            check_lear_realm_query_result(result)

            self.login_user(lear_user)
            create_invitation("general", "newguy2@lear.org", lear_realm)
            result = get_check_query_result("newguy2@lear.org", 1, lear_realm.string_id)
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

    @mock.patch("analytics.views.support.update_billing_method_of_current_plan")
    def test_change_billing_method(self, m: mock.Mock) -> None:
        cordelia = self.example_user("cordelia")
        self.login_user(cordelia)

        result = self.client_post(
            "/activity/support", {"realm_id": f"{cordelia.realm_id}", "plan_type": "2"}
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        iago = self.example_user("iago")
        self.login_user(iago)

        result = self.client_post(
            "/activity/support",
            {"realm_id": f"{iago.realm_id}", "billing_method": "charge_automatically"},
        )
        m.assert_called_once_with(get_realm("zulip"), charge_automatically=True, acting_user=iago)
        self.assert_in_success_response(
            ["Billing method of zulip updated to charge automatically"], result
        )

        m.reset_mock()

        result = self.client_post(
            "/activity/support", {"realm_id": f"{iago.realm_id}", "billing_method": "send_invoice"}
        )
        m.assert_called_once_with(get_realm("zulip"), charge_automatically=False, acting_user=iago)
        self.assert_in_success_response(
            ["Billing method of zulip updated to pay by invoice"], result
        )

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
                ["Plan type of zulip changed from self-hosted to limited"], result
            )

        with mock.patch("analytics.views.support.do_change_realm_plan_type") as m:
            result = self.client_post(
                "/activity/support", {"realm_id": f"{iago.realm_id}", "plan_type": "10"}
            )
            m.assert_called_once_with(get_realm("zulip"), 10, acting_user=iago)
            self.assert_in_success_response(
                ["Plan type of zulip changed from self-hosted to plus"], result
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
        cordelia = self.example_user("cordelia")
        lear_realm = get_realm("lear")
        self.login_user(cordelia)

        result = self.client_post(
            "/activity/support", {"realm_id": f"{lear_realm.id}", "discount": "25"}
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        iago = self.example_user("iago")
        self.login("iago")

        with mock.patch("analytics.views.support.attach_discount_to_realm") as m:
            result = self.client_post(
                "/activity/support", {"realm_id": f"{lear_realm.id}", "discount": "25"}
            )
            m.assert_called_once_with(get_realm("lear"), 25, acting_user=iago)
            self.assert_in_success_response(["Discount of lear changed to 25% from 0%"], result)

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
        lear_realm = get_realm("lear")
        update_sponsorship_status(lear_realm, True, acting_user=None)
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
            ["Subdomain unavailable. Please choose a different one."], result
        )

        result = self.client_post(
            "/activity/support", {"realm_id": f"{lear_realm.id}", "new_subdomain": "zulip"}
        )
        self.assert_in_success_response(
            ["Subdomain unavailable. Please choose a different one."], result
        )

        result = self.client_post(
            "/activity/support", {"realm_id": f"{lear_realm.id}", "new_subdomain": "lear"}
        )
        self.assert_in_success_response(
            ["Subdomain unavailable. Please choose a different one."], result
        )

    def test_downgrade_realm(self) -> None:
        cordelia = self.example_user("cordelia")
        self.login_user(cordelia)
        result = self.client_post(
            "/activity/support", {"realm_id": f"{cordelia.realm_id}", "plan_type": "2"}
        )
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/login/")

        iago = self.example_user("iago")
        self.login_user(iago)

        with mock.patch("analytics.views.support.downgrade_at_the_end_of_billing_cycle") as m:
            result = self.client_post(
                "/activity/support",
                {
                    "realm_id": f"{iago.realm_id}",
                    "modify_plan": "downgrade_at_billing_cycle_end",
                },
            )
            m.assert_called_once_with(get_realm("zulip"))
            self.assert_in_success_response(
                ["zulip marked for downgrade at the end of billing cycle"], result
            )

        with mock.patch(
            "analytics.views.support.downgrade_now_without_creating_additional_invoices"
        ) as m:
            result = self.client_post(
                "/activity/support",
                {
                    "realm_id": f"{iago.realm_id}",
                    "modify_plan": "downgrade_now_without_additional_licenses",
                },
            )
            m.assert_called_once_with(get_realm("zulip"))
            self.assert_in_success_response(
                ["zulip downgraded without creating additional invoices"], result
            )

        with mock.patch(
            "analytics.views.support.downgrade_now_without_creating_additional_invoices"
        ) as m1:
            with mock.patch("analytics.views.support.void_all_open_invoices", return_value=1) as m2:
                result = self.client_post(
                    "/activity/support",
                    {
                        "realm_id": f"{iago.realm_id}",
                        "modify_plan": "downgrade_now_void_open_invoices",
                    },
                )
                m1.assert_called_once_with(get_realm("zulip"))
                m2.assert_called_once_with(get_realm("zulip"))
                self.assert_in_success_response(
                    ["zulip downgraded and voided 1 open invoices"], result
                )

        with mock.patch("analytics.views.support.switch_realm_from_standard_to_plus_plan") as m:
            result = self.client_post(
                "/activity/support",
                {
                    "realm_id": f"{iago.realm_id}",
                    "modify_plan": "upgrade_to_plus",
                },
            )
            m.assert_called_once_with(get_realm("zulip"))
            self.assert_in_success_response(["zulip upgraded to Plus"], result)

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
