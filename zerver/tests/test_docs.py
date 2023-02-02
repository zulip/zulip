import os
import re
from typing import TYPE_CHECKING, Any, Dict, Sequence
from unittest import mock, skipUnless
from urllib.parse import urlsplit

import orjson
from django.conf import settings
from django.test import override_settings
from django.utils.timezone import now as timezone_now

from corporate.models import Customer, CustomerPlan
from zerver.context_processors import get_apps_page_url
from zerver.lib.integrations import CATEGORIES, INTEGRATIONS, META_CATEGORY
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import HostRequestMock
from zerver.models import Realm, get_realm
from zerver.views.documentation import add_api_uri_context

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class DocPageTest(ZulipTestCase):
    def get_doc(self, url: str, subdomain: str) -> "TestHttpResponse":
        if url[0:23] == "/integrations/doc-html/":
            return self.client_get(url, subdomain=subdomain, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        return self.client_get(url, subdomain=subdomain)

    def print_msg_if_error(self, url: str, response: "TestHttpResponse") -> None:  # nocoverage
        if response.status_code == 200:
            return
        print("Error processing URL:", url)
        if response.get("Content-Type") == "application/json":
            content = orjson.loads(response.content)
            print()
            print("======================================================================")
            print("ERROR: {}".format(content.get("msg")))
            print()

    def _test(
        self,
        url: str,
        expected_content: str,
        extra_strings: Sequence[str] = [],
        landing_missing_strings: Sequence[str] = [],
        landing_page: bool = True,
        doc_html_str: bool = False,
    ) -> None:
        # Test the URL on the "zephyr" subdomain
        result = self.get_doc(url, subdomain="zephyr")
        self.print_msg_if_error(url, result)

        self.assertEqual(result.status_code, 200)
        self.assertIn(expected_content, str(result.content))
        for s in extra_strings:
            self.assertIn(s, str(result.content))
        if not doc_html_str:
            self.assert_in_success_response(
                ['<meta name="robots" content="noindex,nofollow" />'], result
            )

        # Test the URL on the root subdomain
        result = self.get_doc(url, subdomain="")
        self.print_msg_if_error(url, result)

        self.assertEqual(result.status_code, 200)
        self.assertIn(expected_content, str(result.content))
        if not doc_html_str:
            self.assert_in_success_response(
                ['<meta name="robots" content="noindex,nofollow" />'], result
            )

        for s in extra_strings:
            self.assertIn(s, str(result.content))

        if not landing_page:
            return
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            # Test the URL on the root subdomain with the landing page setting
            result = self.get_doc(url, subdomain="")
            self.print_msg_if_error(url, result)

            self.assertEqual(result.status_code, 200)
            self.assertIn(expected_content, str(result.content))
            for s in extra_strings:
                self.assertIn(s, str(result.content))
            for s in landing_missing_strings:
                self.assertNotIn(s, str(result.content))
            if not doc_html_str:
                # Confirm page has the following HTML elements:
                self.assert_in_success_response(
                    [
                        "<title>",
                        '<meta name="description" content="',
                        '<meta property="og:title" content="',
                        '<meta property="og:description" content="',
                    ],
                    result,
                )
            self.assert_not_in_success_response(
                ['<meta name="robots" content="noindex,nofollow" />'], result
            )

            # Test the URL on the "zephyr" subdomain with the landing page setting
            result = self.get_doc(url, subdomain="zephyr")
            self.print_msg_if_error(url, result)

            self.assertEqual(result.status_code, 200)
            self.assertIn(expected_content, str(result.content))
            for s in extra_strings:
                self.assertIn(s, str(result.content))
            if not doc_html_str:
                self.assert_in_success_response(
                    ['<meta name="robots" content="noindex,nofollow" />'], result
                )

    def test_api_doc_endpoints(self) -> None:
        # We extract the set of /api/ endpoints to check by parsing
        # the /api/ page sidebar for links starting with /api/.
        api_page_raw = str(self.client_get("/api/").content)
        ENDPOINT_REGEXP = re.compile(r"href=\"/api/\s*(.*?)\"")
        endpoint_list_set = set(re.findall(ENDPOINT_REGEXP, api_page_raw))
        endpoint_list = [f"/api/{endpoint}" for endpoint in endpoint_list_set]
        # Validate that the parsing logic isn't broken, since if it
        # broke, the below would become a noop.
        self.assertGreater(len(endpoint_list), 70)

        for endpoint in endpoint_list:
            self._test(endpoint, "", doc_html_str=True)

        result = self.client_get(
            "/api/nonexistent-page",
            follow=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(result.status_code, 404)

        result = self.client_get(
            # This template shouldn't be accessed directly.
            "/api/api-doc-template",
            follow=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(result.status_code, 404)

        # Test some API doc endpoints for specific content and metadata.
        self._test("/api/", "The Zulip API")
        self._test("/api/api-keys", "be careful with it")
        self._test("/api/installation-instructions", "No download required!")
        self._test("/api/send-message", "steal away your hearts")
        self._test("/api/render-message", "**foo**")
        self._test("/api/get-streams", "include_public")
        self._test("/api/get-stream-id", "The name of the stream to access.")
        self._test("/api/get-subscriptions", "Get all streams that the user is subscribed to.")
        self._test("/api/get-users", "client_gravatar")
        self._test("/api/register-queue", "apply_markdown")
        self._test("/api/get-events", "dont_block")
        self._test("/api/delete-queue", "Delete a previously registered queue")
        self._test("/api/update-message", "propagate_mode")
        self._test("/api/get-own-user", "does not accept any parameters.")
        self._test("/api/subscribe", "authorization_errors_fatal")
        self._test("/api/create-user", "zuliprc-admin")
        self._test("/api/unsubscribe", "not_removed")

    def test_dev_environment_endpoints(self) -> None:
        self._test("/devlogin/", "Normal users", landing_page=False)
        self._test("/devtools/", "Useful development URLs", landing_page=False)
        self._test(
            "/emails/", "manually generate most of the emails by clicking", landing_page=False
        )

    def test_error_endpoints(self) -> None:
        self._test("/errors/404/", "Page not found", landing_page=False)
        self._test("/errors/5xx/", "Internal server error", landing_page=False)

    def test_corporate_portico_endpoints(self) -> None:
        self._test("/team/", "industry veterans")
        self._test("/apps/", "Apps for every platform.")

        self._test("/history/", "Zulip released as open source!")
        # Test the i18n version of one of these pages.
        self._test("/en/history/", "Zulip released as open source!")
        self._test("/values/", "designed our company")
        self._test("/hello/", "Chat for distributed teams", landing_missing_strings=["Log in"])
        self._test("/attribution/", "Website attributions")
        self._test("/communities/", "Open communities directory")
        self._test("/development-community/", "Zulip development community")
        self._test("/features/", "Beautiful messaging")
        self._test("/jobs/", "Work with us")
        self._test("/self-hosting/", "Self-host Zulip")
        self._test("/security/", "TLS encryption")
        self._test("/use-cases/", "Use cases and customer stories")
        self._test("/why-zulip/", "Why Zulip?")
        # /for/... pages
        self._test("/for/open-source/", "for open source projects")
        self._test("/for/events/", "for conferences and events")
        self._test("/for/education/", "education pricing")
        self._test("/for/research/", "for research")
        self._test("/for/business/", "Communication efficiency represents")
        self._test("/for/communities/", "Zulip for communities")
        # case-studies
        self._test("/case-studies/tum/", "Technical University of Munich")
        self._test("/case-studies/ucsd/", "UCSD")
        self._test("/case-studies/rust/", "Rust programming language")
        self._test("/case-studies/recurse-center/", "Recurse Center")
        self._test("/case-studies/lean/", "Lean theorem prover")
        self._test("/case-studies/idrift/", "Case study: iDrift AS")
        self._test("/case-studies/asciidoctor/", "Case study: Asciidoctor")

    def test_open_organizations_endpoint(self) -> None:
        zulip_dev_info = ["Zulip Dev", "great for testing!"]

        result = self.client_get("/communities/")
        self.assert_not_in_success_response(zulip_dev_info, result)

        realm = get_realm("zulip")
        realm.want_advertise_in_communities_directory = True
        realm.save()
        self._test("/communities/", "Open communities directory", extra_strings=zulip_dev_info)

    def test_integration_doc_endpoints(self) -> None:
        self._test(
            "/integrations/",
            "native integrations.",
            extra_strings=[
                "And hundreds more through",
                "Zapier",
                "IFTTT",
            ],
        )

        for integration in INTEGRATIONS.keys():
            url = f"/integrations/doc-html/{integration}"
            self._test(url, "", doc_html_str=True)

        result = self.client_get(
            "/integrations/doc-html/nonexistent_integration",
            follow=True,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(result.status_code, 404)

    def test_integration_pages_open_graph_metadata(self) -> None:
        og_description = '<meta property="og:description" content="Zulip comes with over'

        # Test a particular integration page
        url = "/integrations/doc/github"
        title = '<meta property="og:title" content="GitHub | Zulip integrations" />'
        description = '<meta property="og:description" content="Zulip comes with over'
        self._test(url, title, doc_html_str=True)
        self._test(url, description, doc_html_str=True)

        # Test category pages
        for category in CATEGORIES.keys():
            url = f"/integrations/{category}"
            if category in META_CATEGORY.keys():
                title = f"<title>{CATEGORIES[category]} | Zulip integrations</title>"
                og_title = f'<meta property="og:title" content="{CATEGORIES[category]} | Zulip integrations" />'
            else:
                title = f"<title>{CATEGORIES[category]} tools | Zulip integrations</title>"
                og_title = f'<meta property="og:title" content="{CATEGORIES[category]} tools | Zulip integrations" />'
            self._test(url, title)
            self._test(url, og_title, doc_html_str=True)
            self._test(url, og_description, doc_html_str=True)

        # Test integrations index page
        url = "/integrations/"
        og_title = '<meta property="og:title" content="Zulip integrations" />'
        self._test(url, og_title, doc_html_str=True)
        self._test(url, og_description, doc_html_str=True)

    def test_doc_html_str_non_ajax_call(self) -> None:
        # We don't need to test all the pages for 404
        for integration in list(INTEGRATIONS.keys())[5]:
            with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
                url = f"/en/integrations/doc-html/{integration}"
                result = self.client_get(url, subdomain="", follow=True)
                self.assertEqual(result.status_code, 404)
                result = self.client_get(url, subdomain="zephyr", follow=True)
                self.assertEqual(result.status_code, 404)

            url = f"/en/integrations/doc-html/{integration}"
            result = self.client_get(url, subdomain="", follow=True)
            self.assertEqual(result.status_code, 404)
            result = self.client_get(url, subdomain="zephyr", follow=True)
            self.assertEqual(result.status_code, 404)

        result = self.client_get("/integrations/doc-html/nonexistent_integration", follow=True)
        self.assertEqual(result.status_code, 404)

    def test_electron_detection(self) -> None:
        result = self.client_get("/accounts/password/reset/")
        # TODO: Ideally, this Mozilla would be the specific browser.
        self.assertTrue('data-platform="Mozilla"' in result.content.decode())

        result = self.client_get("/accounts/password/reset/", HTTP_USER_AGENT="ZulipElectron/1.0.0")
        self.assertTrue('data-platform="ZulipElectron"' in result.content.decode())


class HelpTest(ZulipTestCase):
    def test_help_settings_links(self) -> None:
        result = self.client_get("/help/change-the-time-format")
        self.assertEqual(result.status_code, 200)
        self.assertIn(
            'Go to <a href="/#settings/display-settings">Display settings</a>', str(result.content)
        )
        # Check that the sidebar was rendered properly.
        self.assertIn("Getting started with Zulip", str(result.content))

        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.client_get("/help/change-the-time-format", subdomain="")
        self.assertEqual(result.status_code, 200)
        self.assertIn("<strong>Display settings</strong>", str(result.content))
        self.assertNotIn("/#settings", str(result.content))

    def test_help_relative_links_for_gear(self) -> None:
        result = self.client_get("/help/analytics")
        self.assertIn('<a href="/stats">Usage statistics</a>', str(result.content))
        self.assertEqual(result.status_code, 200)

        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.client_get("/help/analytics", subdomain="")
        self.assertEqual(result.status_code, 200)
        self.assertIn("<strong>Usage statistics</strong>", str(result.content))
        self.assertNotIn("/stats", str(result.content))

    def test_help_relative_links_for_stream(self) -> None:
        result = self.client_get("/help/message-a-stream-by-email")
        self.assertIn('<a href="/#streams/subscribed">Subscribed streams</a>', str(result.content))
        self.assertEqual(result.status_code, 200)

        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.client_get("/help/message-a-stream-by-email", subdomain="")
        self.assertEqual(result.status_code, 200)
        self.assertIn("<strong>Manage streams</strong>", str(result.content))
        self.assertNotIn("/#streams", str(result.content))


class IntegrationTest(ZulipTestCase):
    def test_check_if_every_integration_has_logo_that_exists(self) -> None:
        for integration in INTEGRATIONS.values():
            assert integration.logo_url is not None
            path = urlsplit(integration.logo_url).path
            self.assertTrue(os.path.isfile(settings.DEPLOY_ROOT + path), integration.name)

    def test_api_url_view_subdomains_base(self) -> None:
        context: Dict[str, Any] = {}
        add_api_uri_context(context, HostRequestMock())
        self.assertEqual(context["api_url_scheme_relative"], "testserver/api")
        self.assertEqual(context["api_url"], "http://testserver/api")
        self.assertTrue(context["html_settings_links"])

    @override_settings(ROOT_DOMAIN_LANDING_PAGE=True)
    def test_api_url_view_subdomains_homepage_base(self) -> None:
        context: Dict[str, Any] = {}
        add_api_uri_context(context, HostRequestMock())
        self.assertEqual(context["api_url_scheme_relative"], "yourZulipDomain.testserver/api")
        self.assertEqual(context["api_url"], "http://yourZulipDomain.testserver/api")
        self.assertFalse(context["html_settings_links"])

    def test_api_url_view_subdomains_full(self) -> None:
        context: Dict[str, Any] = {}
        request = HostRequestMock(host="mysubdomain.testserver")
        add_api_uri_context(context, request)
        self.assertEqual(context["api_url_scheme_relative"], "mysubdomain.testserver/api")
        self.assertEqual(context["api_url"], "http://mysubdomain.testserver/api")
        self.assertTrue(context["html_settings_links"])

    def test_html_settings_links(self) -> None:
        context: Dict[str, Any] = {}
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            add_api_uri_context(context, HostRequestMock())
        self.assertEqual(context["settings_html"], "Zulip settings page")
        self.assertEqual(context["subscriptions_html"], "streams page")

        context = {}
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            add_api_uri_context(context, HostRequestMock(host="mysubdomain.testserver"))
        self.assertEqual(context["settings_html"], '<a href="/#settings">Zulip settings page</a>')
        self.assertEqual(
            context["subscriptions_html"], '<a target="_blank" href="/#streams">streams page</a>'
        )

        context = {}
        add_api_uri_context(context, HostRequestMock())
        self.assertEqual(context["settings_html"], '<a href="/#settings">Zulip settings page</a>')
        self.assertEqual(
            context["subscriptions_html"], '<a target="_blank" href="/#streams">streams page</a>'
        )


class AboutPageTest(ZulipTestCase):
    @skipUnless(settings.ZILENCER_ENABLED, "requires zilencer")
    def test_endpoint(self) -> None:
        with self.settings(CONTRIBUTOR_DATA_FILE_PATH="zerver/tests/fixtures/authors.json"):
            result = self.client_get("/team/")
        self.assert_in_success_response(["Our amazing community"], result)
        self.assert_in_success_response(["2017-11-20"], result)
        self.assert_in_success_response(["timabbott", "showell", "gnprice", "rishig"], result)

        with mock.patch("corporate.views.portico.open", side_effect=FileNotFoundError) as m:
            result = self.client_get("/team/")
            self.assertEqual(result.status_code, 200)
            self.assert_in_success_response(["Never ran"], result)
            m.assert_called_once()

        with self.settings(ZILENCER_ENABLED=False):
            result = self.client_get("/team/")
            self.assertEqual(result.status_code, 301)
            self.assertEqual(result["Location"], "https://zulip.com/team/")


class SmtpConfigErrorTest(ZulipTestCase):
    def test_smtp_error(self) -> None:
        result = self.client_get("/config-error/smtp")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["email configuration"], result)


class PlansPageTest(ZulipTestCase):
    def test_plans_auth(self) -> None:
        root_domain = ""
        result = self.client_get("/plans/", subdomain=root_domain)
        self.assert_in_success_response(["Self-host Zulip"], result)
        self.assert_not_in_success_response(["/upgrade#sponsorship"], result)
        self.assert_in_success_response(["/accounts/go/?next=%2Fupgrade%23sponsorship"], result)

        non_existent_domain = "moo"
        result = self.client_get("/plans/", subdomain=non_existent_domain)
        self.assertEqual(result.status_code, 404)
        self.assert_in_response("does not exist", result)

        realm = get_realm("zulip")
        realm.plan_type = Realm.PLAN_TYPE_STANDARD_FREE
        realm.save(update_fields=["plan_type"])
        result = self.client_get("/plans/", subdomain="zulip")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/accounts/login/?next=/plans")

        guest_user = "polonius"
        self.login(guest_user)
        result = self.client_get("/plans/", subdomain="zulip", follow=True)
        self.assertEqual(result.status_code, 404)

        organization_member = "hamlet"
        self.login(organization_member)
        result = self.client_get("/plans/", subdomain="zulip")
        self.assert_in_success_response(["Current plan"], result)
        self.assert_in_success_response(["/upgrade#sponsorship"], result)
        self.assert_not_in_success_response(["/accounts/go/?next=%2Fupgrade%23sponsorship"], result)

        # Test root domain, with login on different domain
        result = self.client_get("/plans/", subdomain="")
        # TODO: works in manual testing, but I suspect something is funny in
        # the test environment
        # self.assert_in_success_response(["Sign up now"], result)

    def test_CTA_text_by_plan_type(self) -> None:
        sign_up_now = "Create organization"
        upgrade_to_standard = "Upgrade to Standard"
        current_plan = "Current plan"
        sponsorship_pending = "Sponsorship pending"

        # Root domain
        result = self.client_get("/plans/", subdomain="")
        self.assert_in_success_response([sign_up_now, upgrade_to_standard], result)
        self.assert_not_in_success_response([current_plan, sponsorship_pending], result)

        realm = get_realm("zulip")
        realm.plan_type = Realm.PLAN_TYPE_SELF_HOSTED
        realm.save(update_fields=["plan_type"])

        with self.settings(PRODUCTION=True):
            result = self.client_get("/plans/", subdomain="zulip")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], "https://zulip.com/plans")

            self.login("iago")

            # SELF_HOSTED should hide the local plans page, even if logged in
            result = self.client_get("/plans/", subdomain="zulip")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result["Location"], "https://zulip.com/plans")

        # But in the development environment, it renders a page
        result = self.client_get("/plans/", subdomain="zulip")
        self.assert_in_success_response([sign_up_now, upgrade_to_standard], result)
        self.assert_not_in_success_response([current_plan, sponsorship_pending], result)

        realm.plan_type = Realm.PLAN_TYPE_LIMITED
        realm.save(update_fields=["plan_type"])
        result = self.client_get("/plans/", subdomain="zulip")
        self.assert_in_success_response([current_plan, upgrade_to_standard], result)
        self.assert_not_in_success_response([sign_up_now, sponsorship_pending], result)

        with self.settings(FREE_TRIAL_DAYS=60):
            result = self.client_get("/plans/", subdomain="zulip")
            self.assert_in_success_response([current_plan, "Start 60 day free trial"], result)
            self.assert_not_in_success_response(
                [sign_up_now, sponsorship_pending, upgrade_to_standard], result
            )

        realm.plan_type = Realm.PLAN_TYPE_STANDARD_FREE
        realm.save(update_fields=["plan_type"])
        result = self.client_get("/plans/", subdomain="zulip")
        self.assert_in_success_response([current_plan], result)
        self.assert_not_in_success_response(
            [sign_up_now, upgrade_to_standard, sponsorship_pending], result
        )

        realm.plan_type = Realm.PLAN_TYPE_STANDARD
        realm.save(update_fields=["plan_type"])
        result = self.client_get("/plans/", subdomain="zulip")
        self.assert_in_success_response([current_plan], result)
        self.assert_not_in_success_response(
            [sign_up_now, upgrade_to_standard, sponsorship_pending], result
        )

        customer = Customer.objects.create(realm=get_realm("zulip"), stripe_customer_id="cus_id")
        plan = CustomerPlan.objects.create(
            customer=customer,
            tier=CustomerPlan.STANDARD,
            status=CustomerPlan.FREE_TRIAL,
            billing_cycle_anchor=timezone_now(),
            billing_schedule=CustomerPlan.MONTHLY,
        )
        result = self.client_get("/plans/", subdomain="zulip")
        self.assert_in_success_response(["Current plan (free trial)"], result)
        self.assert_not_in_success_response(
            [sign_up_now, upgrade_to_standard, sponsorship_pending], result
        )

        realm.plan_type = Realm.PLAN_TYPE_LIMITED
        realm.save()
        customer.sponsorship_pending = True
        customer.save()
        plan.delete()
        result = self.client_get("/plans/", subdomain="zulip")
        self.assert_in_success_response([current_plan], result)
        self.assert_in_success_response([current_plan, sponsorship_pending], result)
        self.assert_not_in_success_response([sign_up_now, upgrade_to_standard], result)


class AppsPageTest(ZulipTestCase):
    def test_get_apps_page_url(self) -> None:
        with self.settings(CORPORATE_ENABLED=False):
            apps_page_url = get_apps_page_url()
        self.assertEqual(apps_page_url, "https://zulip.com/apps/")

        with self.settings(CORPORATE_ENABLED=True):
            apps_page_url = get_apps_page_url()
        self.assertEqual(apps_page_url, "/apps/")

    def test_apps_view(self) -> None:
        with self.settings(CORPORATE_ENABLED=False):
            # Note that because this cannot actually uninstall the
            # "corporate" app and trigger updates to URL resolution,
            # this does not test the "apps/" path installed in
            # zproject.urls, but rather the special-case for testing
            # in corporate.views.portico
            result = self.client_get("/apps")
            self.assertEqual(result.status_code, 301)
            self.assertTrue(result["Location"].endswith("/apps/"))

            result = self.client_get("/apps/")
            self.assertEqual(result.status_code, 301)
            self.assertTrue(result["Location"] == "https://zulip.com/apps/")

            result = self.client_get("/apps/linux")
            self.assertEqual(result.status_code, 301)
            self.assertTrue(result["Location"] == "https://zulip.com/apps/")

        with self.settings(CORPORATE_ENABLED=True):
            result = self.client_get("/apps")
            self.assertEqual(result.status_code, 301)
            self.assertTrue(result["Location"].endswith("/apps/"))

            result = self.client_get("/apps/")
            self.assertEqual(result.status_code, 200)
            html = result.content.decode()
            self.assertIn("Apps for every platform.", html)

    def test_app_download_link_view(self) -> None:
        return_value = "https://desktop-download.zulip.com/v5.4.3/Zulip-Web-Setup-5.4.3.exe"
        with mock.patch(
            "corporate.views.portico.get_latest_github_release_download_link_for_platform",
            return_value=return_value,
        ) as m:
            result = self.client_get("/apps/download/windows")
            m.assert_called_once_with("windows")
            self.assertEqual(result.status_code, 302)
            self.assertTrue(result["Location"] == return_value)

        result = self.client_get("/apps/download/plan9")
        self.assertEqual(result.status_code, 404)


class PrivacyTermsTest(ZulipTestCase):
    def test_terms_and_policies_index(self) -> None:
        with self.settings(POLICIES_DIRECTORY="corporate/policies"):
            response = self.client_get("/policies/")
        self.assert_in_success_response(["Terms and policies"], response)

    def test_custom_terms_of_service_template(self) -> None:
        not_configured_message = "This server is an installation"
        with self.settings(POLICIES_DIRECTORY="zerver/policies_absent"):
            response = self.client_get("/policies/terms")
        self.assert_in_response(not_configured_message, response)

        with self.settings(POLICIES_DIRECTORY="corporate/policies"):
            response = self.client_get("/policies/terms")
        self.assert_in_success_response(["Kandra Labs"], response)

    def test_custom_privacy_policy_template(self) -> None:
        not_configured_message = "This server is an installation"
        with self.settings(POLICIES_DIRECTORY="zerver/policies_absent"):
            response = self.client_get("/policies/privacy")
        self.assert_in_response(not_configured_message, response)

        with self.settings(POLICIES_DIRECTORY="corporate/policies"):
            response = self.client_get("/policies/privacy")
        self.assert_in_success_response(["Kandra Labs"], response)

    def test_custom_privacy_policy_template_with_absolute_url(self) -> None:
        """Verify that using our recommended production default of an absolute path
        like /etc/zulip/policies/ works."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        abs_path = os.path.abspath(
            os.path.join(current_dir, "..", "..", "templates/corporate/policies")
        )
        with self.settings(POLICIES_DIRECTORY=abs_path):
            response = self.client_get("/policies/privacy")
        self.assert_in_success_response(["Kandra Labs"], response)

        with self.settings(POLICIES_DIRECTORY=abs_path):
            response = self.client_get("/policies/nonexistent")
        self.assert_in_response("No such page", response)

    def test_redirects_from_older_urls(self) -> None:
        with self.settings(POLICIES_DIRECTORY="corporate/policies"):
            result = self.client_get("/privacy/", follow=True)
        self.assert_in_success_response(["Kandra Labs"], result)

        with self.settings(POLICIES_DIRECTORY="corporate/policies"):
            result = self.client_get("/terms/", follow=True)
        self.assert_in_success_response(["Kandra Labs"], result)

    def test_no_nav(self) -> None:
        # Test that our ?nav=0 feature of /privacy and /terms,
        # designed to comply with the Apple App Store draconian
        # policies that ToS/Privacy pages linked from an iOS app have
        # no links to the rest of the site if there's pricing
        # information for anything elsewhere on the site.

        # We don't have this link at all on these pages; this first
        # line of the test would change if we were to adjust the
        # design.
        response = self.client_get("/policies/terms")
        self.assert_not_in_success_response(["Back to Zulip"], response)

        response = self.client_get("/policies/terms", {"nav": "no"})
        self.assert_not_in_success_response(["Back to Zulip"], response)

        response = self.client_get("/policies/privacy", {"nav": "no"})
        self.assert_not_in_success_response(["Back to Zulip"], response)
