# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os

from django.test import TestCase
from typing import Any

from zproject.settings import DEPLOY_ROOT
from zerver.lib.integrations import INTEGRATIONS
from zerver.views.integrations import add_api_uri_context

class RequestMock(object):
    pass

class IntegrationTest(TestCase):
    def test_check_if_every_integration_has_logo_that_exists(self):
        # type: () -> None
        for integration in INTEGRATIONS.values():
            self.assertTrue(os.path.isfile(os.path.join(DEPLOY_ROOT, integration.logo)))

    def test_api_url_view_base(self):
        # type: () -> None
        context = dict()  # type: Dict[str, Any]
        add_api_uri_context(context, RequestMock())
        self.assertEqual(context["external_api_path_subdomain"], "localhost:9991/api")
        self.assertEqual(context["external_api_uri_subdomain"], "http://localhost:9991/api")
