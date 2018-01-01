# -*- coding: utf-8 -*-

import mock
import os
import subprocess

from django.conf import settings
from django.test import TestCase, override_settings
from typing import Any, Dict, List

from zproject.settings import DEPLOY_ROOT
from zerver.lib.integrations import INTEGRATIONS
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import HostRequestMock
from zerver.lib.test_runner import slow
from zerver.lib.utils import split_by
from zerver.views.integrations import (
    add_api_uri_context,
    add_integrations_context,
)

class DocPageTest(ZulipTestCase):
    def _test(self, url: str, expected_content: str, extra_strings: List[str]=[],
              landing_missing_strings: List[str]=[], landing_page: bool=True) -> None:

        # Test the URL on the "zulip" subdomain
        result = self.client_get(url, subdomain="zulip")
        self.assertEqual(result.status_code, 200)
        self.assertIn(expected_content, str(result.content))
        for s in extra_strings:
            self.assertIn(s, str(result.content))

        # Test the URL on the root subdomain
        result = self.client_get(url, subdomain="")
        self.assertEqual(result.status_code, 200)
        self.assertIn(expected_content, str(result.content))
        for s in extra_strings:
            self.assertIn(s, str(result.content))

        if not landing_page:
            return
        # Test the URL on the root subdomain with the landing page setting
        with self.settings(ROOT_DOMAIN_LANDING_PAGE=True):
            result = self.client_get(url, subdomain="")
            self.assertEqual(result.status_code, 200)
            self.assertIn(expected_content, str(result.content))
            for s in extra_strings:
                self.assertIn(s, str(result.content))
            for s in landing_missing_strings:
                self.assertNotIn(s, str(result.content))

    @slow("Tests dozens of endpoints, including generating lots of emails")
    def test_doc_endpoints(self) -> None:
        self._test('/api/', 'We hear you like APIs')
        self._test('/api/endpoints/', 'pre-built API bindings for')
        self._test('/api/api-keys', 'you can use its email and API key')
        self._test('/api/installation-instructions', 'No download required!')
        self._test('/api/private-message', 'steal away your hearts')
        self._test('/api/stream-message', 'rotten in the state of Denmark')
        self._test('/api/render-message', '**foo**')
        self._test('/api/get-all-streams', 'include_public')
        self._test('/api/get-stream-id', 'The name of the stream to retrieve the ID for.')
        self._test('/api/get-subscribed-streams', 'Get all streams that the user is subscribed to.')
        self._test('/api/get-all-users', 'client_gravatar')
        self._test('/team/', 'industry veterans')
        self._test('/history/', 'Cambridge, Massachusetts')
        # Test the i18n version of one of these pages.
        self._test('/en/history/', 'Cambridge, Massachusetts')
        self._test('/apps/', 'Apps for every platform.')
        self._test('/features/', 'Beautiful messaging')
        self._test('/hello/', 'productive group chat', landing_missing_strings=["Login"])
        self._test('/why-zulip/', 'all stakeholders can see and')
        self._test('/for/open-source/', 'for open source projects')
        self._test('/for/companies/', 'in a company')
        self._test('/for/working-groups-and-communities/', 'standards bodies')
        self._test('/for/mystery-hunt/', 'four SIPB alums')
        self._test('/plans/', 'Community support')
        self._test('/devlogin/', 'Normal users', landing_page=False)
        self._test('/devtools/', 'Useful development URLs')
        self._test('/errors/404/', 'Page not found')
        self._test('/errors/5xx/', 'Internal server error')
        self._test('/emails/', 'manually generate most of the emails by clicking')

        result = self.client_get('/integrations/doc-html/nonexistent_integration', follow=True)
        self.assertEqual(result.status_code, 404)

        result = self.client_get('/new-user/')
        self.assertEqual(result.status_code, 301)
        self.assertIn('hello', result['Location'])

        result = self.client_get('/static/favicon.ico')
        self.assertEqual(result.status_code, 200)

    @slow("Tests dozens of endpoints, including all our integrations docs")
    def test_integration_doc_endpoints(self) -> None:
        self._test('/integrations/',
                   'Over 60 native integrations.',
                   extra_strings=[
                       'And hundreds more through',
                       'Hubot',
                       'Zapier',
                       'IFTTT'
                   ])

        for integration in INTEGRATIONS.keys():
            url = '/integrations/doc-html/{}'.format(integration)
            self._test(url, '')


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

    def test_integration_view_html_settings_links(self) -> None:
        context = dict()
        context['html_settings_links'] = False
        add_integrations_context(context)
        self.assertEqual(
            context['settings_html'],
            'Zulip settings page')
        self.assertEqual(
            context['subscriptions_html'],
            'streams page')

        context = dict()
        context['html_settings_links'] = True
        add_integrations_context(context)
        self.assertEqual(
            context['settings_html'],
            '<a href="../../#settings">Zulip settings page</a>')
        self.assertEqual(
            context['subscriptions_html'],
            '<a target="_blank" href="../../#streams">streams page</a>')

class AboutPageTest(ZulipTestCase):
    def setUp(self) -> None:
        """ Manual installation which did not execute `tools/provision`
        would not have the `static/generated/github-contributors.json` fixture
        file.
        """
        # This block has unreliable test coverage due to the implicit
        # caching here, so we exclude it from coverage.
        if not os.path.exists(settings.CONTRIBUTORS_DATA):
            # Copy the fixture file in `zerver/fixtures` to `static/generated`
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
