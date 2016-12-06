# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os

from django.conf import settings
from django.test import TestCase, override_settings
from typing import Any

from zproject.settings import DEPLOY_ROOT
from zerver.lib.integrations import INTEGRATIONS, HUBOT_LOZENGES
from zerver.lib.test_helpers import HostRequestMock
from zerver.views.integrations import add_api_uri_context

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

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_api_url_view_subdomains_base(self):
        # type: () -> None
        context = dict()  # type: Dict[str, Any]
        add_api_uri_context(context, HostRequestMock())
        self.assertEqual(context["external_api_path_subdomain"], "yourZulipDomain.testserver/api")
        self.assertEqual(context["external_api_uri_subdomain"], "http://yourZulipDomain.testserver/api")

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_api_url_view_subdomains_full(self):
        # type: () -> None
        context = dict()  # type: Dict[str, Any]
        request = HostRequestMock(host="mysubdomain.testserver")
        add_api_uri_context(context, request)
        self.assertEqual(context["external_api_path_subdomain"], "mysubdomain.testserver/api")
        self.assertEqual(context["external_api_uri_subdomain"], "http://mysubdomain.testserver/api")
