# -*- coding: utf-8 -*-

import os
import subprocess
import ujson

from django.conf import settings
from django.test import TestCase, override_settings
from django.http import HttpResponse
from typing import Any, Dict, List

from zproject.settings import DEPLOY_ROOT
from zerver.lib.integrations import INTEGRATIONS
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import HostRequestMock
from zerver.lib.test_runner import slow
from zerver.lib.utils import split_by
from zerver.models import Realm, get_realm
from zerver.views.documentation import (
    add_api_uri_context,
)

class DocPageTest(ZulipTestCase):
    def get_doc(self, url: str, subdomain: str) -> HttpResponse:
        if url[0:23] == "/integrations/doc-html/":
            return self.client_get(url, subdomain=subdomain, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        return self.client_get(url, subdomain=subdomain)

    def print_msg_if_error(self, response: HttpResponse) -> None:  # nocoverage
        if response.status_code != 200 and response.get('Content-Type') == 'application/json':
            content = ujson.loads(response.content)
            print()
            print("======================================================================")
            print("ERROR: {}".format(content.get('msg')))
            print()

    def _test(self, url: str, expected_content: str, extra_strings: List[str]=[],
              landing_missing_strings: List[str]=[], landing_page: bool=True,
              doc_html_str: bool=False) -> None:

        # Test the URL on the "zephyr" subdomain
        result = self.get_doc(url, subdomain="zephyr")
        self.print_msg_if_error(result)

        self.assertEqual(result.status_code, 200)
        self.assertIn(expected_content, str(result.content))
        for s in extra_strings:
            self.assertIn(s, str(result.content))
        if not doc_html_str:
            self.assert_in_success_response(['<meta name="robots" content="noindex,nofollow">'], result)

        # Test the URL on the root subdomain
        result = self.get_doc(url, subdomain="")
        self.print_msg_if_error(result)

        self.assertEqual(result.status_code, 200)
        self.assertIn(expected_content, str(result.content))
        if not doc_html_str:
            self.assert_in_success_response(['<meta name="robots" content="noindex,nofollow">'], result)

        for s in extra_strings:
            self.assertIn(s, str(result.content))

        if not landing_page:
            return
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            # Test the URL on the root subdomain with the landing page setting
            result = self.get_doc(url, subdomain="")
            self.print_msg_if_error(result)

            self.assertEqual(result.status_code, 200)
            self.assertIn(expected_content, str(result.content))
            for s in extra_strings:
                self.assertIn(s, str(result.content))
            for s in landing_missing_strings:
                self.assertNotIn(s, str(result.content))
            if not doc_html_str:
                self.assert_in_success_response(['<meta name="description" content="Zulip combines'], result)
            self.assert_not_in_success_response(['<meta name="robots" content="noindex,nofollow">'], result)

            # Test the URL on the "zephyr" subdomain with the landing page setting
            result = self.get_doc(url, subdomain="zephyr")
            self.print_msg_if_error(result)

            self.assertEqual(result.status_code, 200)
            self.assertIn(expected_content, str(result.content))
            for s in extra_strings:
                self.assertIn(s, str(result.content))
            if not doc_html_str:
                self.assert_in_success_response(['<meta name="robots" content="noindex,nofollow">'], result)

    @slow("Tests dozens of endpoints, including generating lots of emails")
    def test_doc_endpoints(self) -> None:
        self._test('/api/', 'The Zulip API')
        self._test('/api/api-keys', 'be careful with it')
        self._test('/api/installation-instructions', 'No download required!')
        self._test('/api/send-message', 'steal away your hearts')
        self._test('/api/render-message', '**foo**')
        self._test('/api/get-all-streams', 'include_public')
        self._test('/api/get-stream-id', 'The name of the stream to retrieve the ID for.')
        self._test('/api/get-subscribed-streams', 'Get all streams that the user is subscribed to.')
        self._test('/api/get-all-users', 'client_gravatar')
        self._test('/api/register-queue', 'apply_markdown')
        self._test('/api/get-events-from-queue', 'dont_block')
        self._test('/api/delete-queue', 'Delete a previously registered queue')
        self._test('/api/update-message', 'propagate_mode')
        self._test('/api/get-profile', 'takes no arguments')
        self._test('/api/add-subscriptions', 'authorization_errors_fatal')
        self._test('/api/create-user', 'zuliprc-admin')
        self._test('/api/remove-subscriptions', 'not_subscribed')
        self._test('/team/', 'industry veterans')
        self._test('/history/', 'Cambridge, Massachusetts')
        # Test the i18n version of one of these pages.
        self._test('/en/history/', 'Cambridge, Massachusetts')
        self._test('/apps/', 'Apps for every platform.')
        self._test('/features/', 'Beautiful messaging')
        self._test('/hello/', 'productive team chat', landing_missing_strings=["Login"])
        self._test('/why-zulip/', 'Why Zulip?')
        self._test('/for/open-source/', 'for open source projects')
        self._test('/for/companies/', 'in a company')
        self._test('/for/working-groups-and-communities/', 'standards bodies')
        self._test('/for/mystery-hunt/', 'four SIPB alums')
        self._test('/security/', 'TLS encryption')
        self._test('/atlassian/', 'HipChat')
        self._test('/devlogin/', 'Normal users', landing_page=False)
        self._test('/devtools/', 'Useful development URLs')
        self._test('/errors/404/', 'Page not found')
        self._test('/errors/5xx/', 'Internal server error')
        self._test('/emails/', 'manually generate most of the emails by clicking')

        result = self.client_get('/integrations/doc-html/nonexistent_integration', follow=True,
                                 HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(result.status_code, 404)

        result = self.client_get('/new-user/')
        self.assertEqual(result.status_code, 301)
        self.assertIn('hello', result['Location'])

        result = self.client_get('/static/favicon.ico')
        self.assertEqual(result.status_code, 200)

    @slow("Tests dozens of endpoints, including all our integrations docs")
    def test_integration_doc_endpoints(self) -> None:
        self._test('/integrations/',
                   'native integrations.',
                   extra_strings=[
                       'And hundreds more through',
                       'Hubot',
                       'Zapier',
                       'IFTTT'
                   ])

        for integration in INTEGRATIONS.keys():
            url = '/integrations/doc-html/{}'.format(integration)
            self._test(url, '', doc_html_str=True)

    def test_email_integration(self) -> None:
        self._test('/integrations/doc-html/email',
                   'support+abcdefg@testserver', doc_html_str=True)

        with self.settings(EMAIL_GATEWAY_PATTERN=''):
            result = self.get_doc('integrations/doc-html/email', subdomain='zulip')
            self.assertNotIn('support+abcdefg@testserver', str(result.content))
            # if EMAIL_GATEWAY_PATTERN is empty, the main /integrations page should
            # be rendered instead
            self._test('/integrations/', 'native integrations.')

    def test_doc_html_str_non_ajax_call(self) -> None:
        # We don't need to test all the pages for 404
        for integration in list(INTEGRATIONS.keys())[5]:
            with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
                url = '/en/integrations/doc-html/{}'.format(integration)
                result = self.client_get(url, subdomain="", follow=True)
                self.assertEqual(result.status_code, 404)
                result = self.client_get(url, subdomain="zephyr", follow=True)
                self.assertEqual(result.status_code, 404)

            url = '/en/integrations/doc-html/{}'.format(integration)
            result = self.client_get(url, subdomain="", follow=True)
            self.assertEqual(result.status_code, 404)
            result = self.client_get(url, subdomain="zephyr", follow=True)
            self.assertEqual(result.status_code, 404)

        result = self.client_get('/integrations/doc-html/nonexistent_integration', follow=True)
        self.assertEqual(result.status_code, 404)

class HelpTest(ZulipTestCase):
    def test_help_settings_links(self) -> None:
        result = self.client_get('/help/change-the-time-format')
        self.assertEqual(result.status_code, 200)
        self.assertIn('Go to <a href="/#settings/display-settings">Display settings</a>', str(result.content))
        # Check that the sidebar was rendered properly.
        self.assertIn('Getting started with Zulip', str(result.content))

        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.client_get('/help/change-the-time-format', subdomain="")
        self.assertEqual(result.status_code, 200)
        self.assertIn('<strong>Display settings</strong>', str(result.content))
        self.assertNotIn('/#settings', str(result.content))

    def test_help_relative_links_for_gear(self) -> None:
        result = self.client_get('/help/analytics')
        self.assertIn('<a href="/stats">Statistics</a>', str(result.content))
        self.assertEqual(result.status_code, 200)

        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.client_get('/help/analytics', subdomain="")
        self.assertEqual(result.status_code, 200)
        self.assertIn('<strong>Statistics</strong>', str(result.content))
        self.assertNotIn('/stats', str(result.content))

    def test_help_relative_links_for_stream(self) -> None:
        result = self.client_get('/help/message-a-stream-by-email')
        self.assertIn('<a href="/#streams/subscribed">Your streams</a>', str(result.content))
        self.assertEqual(result.status_code, 200)

        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.client_get('/help/message-a-stream-by-email', subdomain="")
        self.assertEqual(result.status_code, 200)
        self.assertIn('<strong>Manage streams</strong>', str(result.content))
        self.assertNotIn('/#streams', str(result.content))

class IntegrationTest(TestCase):
    def test_check_if_every_integration_has_logo_that_exists(self) -> None:
        for integration in INTEGRATIONS.values():
            self.assertTrue(os.path.isfile(os.path.join(DEPLOY_ROOT, integration.logo)))

    def test_api_url_view_subdomains_base(self) -> None:
        context = dict()  # type: Dict[str, Any]
        add_api_uri_context(context, HostRequestMock())
        self.assertEqual(context["api_url_scheme_relative"], "testserver/api")
        self.assertEqual(context["api_url"], "http://testserver/api")
        self.assertTrue(context["html_settings_links"])

    @override_settings(ROOT_DOMAIN_LANDING_PAGE=True)
    def test_api_url_view_subdomains_homepage_base(self) -> None:
        context = dict()  # type: Dict[str, Any]
        add_api_uri_context(context, HostRequestMock())
        self.assertEqual(context["api_url_scheme_relative"], "yourZulipDomain.testserver/api")
        self.assertEqual(context["api_url"], "http://yourZulipDomain.testserver/api")
        self.assertFalse(context["html_settings_links"])

    def test_api_url_view_subdomains_full(self) -> None:
        context = dict()  # type: Dict[str, Any]
        request = HostRequestMock(host="mysubdomain.testserver")
        add_api_uri_context(context, request)
        self.assertEqual(context["api_url_scheme_relative"], "mysubdomain.testserver/api")
        self.assertEqual(context["api_url"], "http://mysubdomain.testserver/api")
        self.assertTrue(context["html_settings_links"])

    def test_html_settings_links(self) -> None:
        context = dict()  # type: Dict[str, Any]
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            add_api_uri_context(context, HostRequestMock())
        self.assertEqual(
            context['settings_html'],
            'Zulip settings page')
        self.assertEqual(
            context['subscriptions_html'],
            'streams page')

        context = dict()
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            add_api_uri_context(context, HostRequestMock(host="mysubdomain.testserver"))
        self.assertEqual(
            context['settings_html'],
            '<a href="/#settings">Zulip settings page</a>')
        self.assertEqual(
            context['subscriptions_html'],
            '<a target="_blank" href="/#streams">streams page</a>')

        context = dict()
        add_api_uri_context(context, HostRequestMock())
        self.assertEqual(
            context['settings_html'],
            '<a href="/#settings">Zulip settings page</a>')
        self.assertEqual(
            context['subscriptions_html'],
            '<a target="_blank" href="/#streams">streams page</a>')

class AboutPageTest(ZulipTestCase):
    def setUp(self) -> None:
        """ Manual installation which did not execute `tools/provision`
        would not have the `static/generated/github-contributors.json` fixture
        file.
        """
        # This block has unreliable test coverage due to the implicit
        # caching here, so we exclude it from coverage.
        if not os.path.exists(settings.CONTRIBUTORS_DATA):
            # Copy the fixture file in `zerver/tests/fixtures` to `static/generated`
            update_script = os.path.join(os.path.dirname(__file__),
                                         '../../tools/update-authors-json')  # nocoverage
            subprocess.check_call([update_script, '--use-fixture'])  # nocoverage

    def test_endpoint(self) -> None:
        """ We can't check the contributors list since it is rendered client-side """
        result = self.client_get('/team/')
        self.assert_in_success_response(['Our amazing community'], result)

    def test_split_by(self) -> None:
        """Utility function primarily used in authors page"""
        flat_list = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        expected_result = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        self.assertEqual(split_by(flat_list, 3, None), expected_result)

class ConfigErrorTest(ZulipTestCase):
    @override_settings(GOOGLE_OAUTH2_CLIENT_ID=None)
    def test_google(self) -> None:
        result = self.client_get("/accounts/login/google/")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, '/config-error/google')
        result = self.client_get(result.url)
        self.assert_in_success_response(["GOOGLE_OAUTH2_CLIENT_ID"], result)

    @override_settings(SOCIAL_AUTH_GITHUB_KEY=None)
    def test_github(self) -> None:
        result = self.client_get("/accounts/login/social/github")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, '/config-error/github')
        result = self.client_get(result.url)
        self.assert_in_success_response(["SOCIAL_AUTH_GITHUB_KEY"], result)

    @override_settings(SOCIAL_AUTH_GITHUB_KEY=None)
    @override_settings(DEVELOPMENT=False)
    def test_github_production_error(self) -> None:
        """Test the !DEVELOPMENT code path of config-error."""
        result = self.client_get("/accounts/login/social/github")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, '/config-error/github')
        result = self.client_get(result.url)
        self.assert_in_success_response(["/etc/zulip/zulip-secrets.conf"], result)

    def test_smtp_error(self) -> None:
        result = self.client_get("/config-error/smtp")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["email configuration"], result)

    def test_dev_direct_production_error(self) -> None:
        result = self.client_get("/config-error/dev")
        self.assertEqual(result.status_code, 200)
        self.assert_in_success_response(["DevAuthBackend"], result)

class PlansPageTest(ZulipTestCase):
    def test_plans_auth(self) -> None:
        # Test root domain
        result = self.client_get("/plans/", subdomain="")
        self.assert_in_success_response(["Sign up now"], result)
        # Test non-existant domain
        result = self.client_get("/plans/", subdomain="moo")
        self.assert_in_success_response(["does not exist"], result)
        # Test valid domain, no login
        realm = get_realm("zulip")
        realm.plan_type = Realm.STANDARD_FREE
        realm.save(update_fields=["plan_type"])
        result = self.client_get("/plans/", subdomain="zulip")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "/accounts/login/?next=plans")
        # Test valid domain, with login
        self.login(self.example_email('hamlet'))
        result = self.client_get("/plans/", subdomain="zulip")
        self.assert_in_success_response(["Current plan"], result)
        # Test root domain, with login on different domain
        result = self.client_get("/plans/", subdomain="")
        # TODO: works in manual testing, but I suspect something is funny in
        # the test environment
        # self.assert_in_success_response(["Sign up now"], result)

    def test_CTA_text_by_plan_type(self) -> None:
        sign_up_now = "Sign up now"
        buy_standard = "Buy Standard"
        current_plan = "Current plan"

        # Root domain
        result = self.client_get("/plans/", subdomain="")
        self.assert_in_success_response([sign_up_now, buy_standard], result)
        self.assert_not_in_success_response([current_plan], result)

        realm = get_realm("zulip")
        realm.plan_type = Realm.SELF_HOSTED
        realm.save(update_fields=["plan_type"])
        result = self.client_get("/plans/", subdomain="zulip")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "https://zulipchat.com/plans")

        self.login(self.example_email("iago"))

        # SELF_HOSTED should hide the local plans page, even if logged in
        result = self.client_get("/plans/", subdomain="zulip")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result["Location"], "https://zulipchat.com/plans")

        realm.plan_type = Realm.LIMITED
        realm.save(update_fields=["plan_type"])
        result = self.client_get("/plans/", subdomain="zulip")
        self.assert_in_success_response([current_plan, buy_standard], result)
        self.assert_not_in_success_response([sign_up_now], result)

        realm.plan_type = Realm.STANDARD_FREE
        realm.save(update_fields=["plan_type"])
        result = self.client_get("/plans/", subdomain="zulip")
        self.assert_in_success_response([current_plan], result)
        self.assert_not_in_success_response([sign_up_now, buy_standard], result)

        realm.plan_type = Realm.STANDARD
        realm.save(update_fields=["plan_type"])
        result = self.client_get("/plans/", subdomain="zulip")
        self.assert_in_success_response([current_plan], result)
        self.assert_not_in_success_response([sign_up_now, buy_standard], result)
