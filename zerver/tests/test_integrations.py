# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os

from django.conf import settings
from django.test import TestCase, override_settings
from typing import Any, Dict

from zproject.settings import DEPLOY_ROOT
from zerver.lib.integrations import INTEGRATIONS, HUBOT_LOZENGES
from zerver.lib.test_helpers import HostRequestMock
from zerver.views.integrations import (
    add_api_uri_context,
    add_integrations_context,
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
            'subscriptions page')

        context = dict()
        context['html_settings_links'] = True
        add_integrations_context(context)
        self.assertEqual(
            context['settings_html'],
            '<a href="../#settings">Zulip settings page</a>')
        self.assertEqual(
            context['subscriptions_html'],
            '<a target="_blank" href="../#subscriptions">subscriptions page</a>')
