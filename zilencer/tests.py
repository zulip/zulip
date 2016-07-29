# -*- coding: utf-8 -*-
from __future__ import absolute_import

import ujson

from django.test import TestCase

class EndpointDiscoveryTest(TestCase):
    def test_staging_user(self):
        # type: () -> None
        response = self.client.get("/api/v1/deployments/endpoints", {"email": "lfaraone@zulip.com"})
        data = ujson.loads(response.content)
        self.assertEqual(data["result"]["base_site_url"], "https://zulip.com/")
        self.assertEqual(data["result"]["base_api_url"], "https://zulip.com/api/")

    def test_prod_user(self):
        # type: () -> None
        response = self.client.get("/api/v1/deployments/endpoints", {"email": "lfaraone@mit.edu"})
        data = ujson.loads(response.content)
        self.assertEqual(data["result"]["base_site_url"], "https://zulip.com/")
        self.assertEqual(data["result"]["base_api_url"], "https://api.zulip.com/")

