# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
from django.test import TestCase
from zproject.settings import DEPLOY_ROOT
from zerver.lib.integrations import INTEGRATIONS


class IntegrationTestCase(TestCase):
    def test_check_if_every_integration_has_logo_that_exists(self):
        for integration in INTEGRATIONS.values():
            self.assertTrue(os.path.isfile(os.path.join(DEPLOY_ROOT, integration.logo)))
