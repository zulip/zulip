# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import subprocess

from django.conf import settings
from django.test import TestCase, override_settings
from typing import Any, Dict

from zproject.settings import DEPLOY_ROOT
from zerver.lib.integrations import INTEGRATIONS, HUBOT_LOZENGES
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import HostRequestMock
from zerver.lib.utils import split_by
from zerver.views.integrations import (
    add_api_uri_context,
    add_integrations_context,
)

class DocPageTest(ZulipTestCase):
        def _test(self, url, expected_content):
            # type: (str, str) -> None
            result = self.client_get(url)
            self.assertEqual(result.status_code, 200)
            self.assertIn(expected_content, str(result.content))

        def test_doc_endpoints(self):
            # type: () -> None
            self._test('/api/', 'We hear you like APIs')
            self._test('/api/endpoints/', 'pre-built API bindings for')
            self._test('/about/', 'Cambridge, Massachusetts')
            # Test the i18n version of one of these pages.
            self._test('/en/about/', 'Cambridge, Massachusetts')
            self._test('/apps/', 'Appsolutely')
            self._test('/features/', 'Talk about multiple topics at once')
            self._test('/hello/', 'workplace chat that actually improves your productivity')
            self._test('/integrations/', 'require creating a Zulip bot')
            self._test('/login/', '(Normal users)')
            self._test('/register/', 'get started')

            result = self.client_get('/new-user/')
            self.assertEqual(result.status_code, 301)
            self.assertIn('hello', result['Location'])

            result = self.client_get('/robots.txt')
            self.assertEqual(result.status_code, 301)
            self.assertIn('static/robots.txt', result['Location'])

            result = self.client_get('/static/robots.txt')
            self.assertEqual(result.status_code, 200)
            self.assertIn(
                'Disallow: /',
                ''.join(str(x) for x in list(result.streaming_content))
            )

class IntegrationTest(TestCase):
    def test_check_if_every_integration_has_logo_that_exists(self):
        # type: () -> None
        for integration in INTEGRATIONS.values():
            self.assertTrue(os.path.isfile(os.path.join(DEPLOY_ROOT, integration.logo)))

    def test_check_if_every_hubot_lozenges_has_logo_that_exists(self):
        # type: () -> None
        for integration in HUBOT_LOZENGES.values():
            self.assertTrue(os.path.isfile(os.path.join(DEPLOY_ROOT, integration.logo)))

    @override_settings(REALMS_HAVE_SUBDOMAINS=False)
    def test_api_url_view_base(self):
        # type: () -> None
        context = dict()  # type: Dict[str, Any]
        add_api_uri_context(context, HostRequestMock())
        self.assertEqual(context["external_api_path_subdomain"], "testserver/api")
        self.assertEqual(context["external_api_uri_subdomain"], "http://testserver/api")
        self.assertTrue(context["html_settings_links"])

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_api_url_view_subdomains_base(self):
        # type: () -> None
        context = dict()  # type: Dict[str, Any]
        add_api_uri_context(context, HostRequestMock())
        self.assertEqual(context["external_api_path_subdomain"], "yourZulipDomain.testserver/api")
        self.assertEqual(context["external_api_uri_subdomain"], "http://yourZulipDomain.testserver/api")
        self.assertFalse(context["html_settings_links"])

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_api_url_view_subdomains_full(self):
        # type: () -> None
        context = dict()  # type: Dict[str, Any]
        request = HostRequestMock(host="mysubdomain.testserver")
        add_api_uri_context(context, request)
        self.assertEqual(context["external_api_path_subdomain"], "mysubdomain.testserver/api")
        self.assertEqual(context["external_api_uri_subdomain"], "http://mysubdomain.testserver/api")
        self.assertTrue(context["html_settings_links"])

    def test_integration_view_html_settings_links(self):
        # type: () -> None
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
            '<a href="../#settings">Zulip settings page</a>')
        self.assertEqual(
            context['subscriptions_html'],
            '<a target="_blank" href="../#streams">streams page</a>')

class AuthorsPageTest(ZulipTestCase):
    def setUp(self):
        # type: () -> None
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

    def test_endpoint(self):
        # type: () -> None
        result = self.client_get('/authors/')
        self.assert_in_success_response(
            ['Contributors', 'Statistic last Updated:', 'commits',
             '@timabbott'],
            result
        )

    def test_split_by(self):
        # type: () -> None
        """Utility function primarily used in authors page"""
        flat_list = [1, 2, 3, 4, 5, 6, 7]
        expected_result = [[1, 2], [3, 4], [5, 6], [7, None]]
        self.assertEqual(split_by(flat_list, 2, None), expected_result)
