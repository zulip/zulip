# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

import django.core.urlresolvers
from django.test import TestCase
import importlib
from zproject import urls

class URLResolutionTest(TestCase):
    def check_function_exists(self, module_name, view):
        module = importlib.import_module(module_name)
        self.assertTrue(hasattr(module, view), "View %s.%s does not exist" % (module_name, view))

    # Tests that all views in urls.v1_api_and_json_patterns exist
    def test_rest_api_url_resolution(self):
        for pattern in urls.v1_api_and_json_patterns:
            if not (hasattr(pattern, "_callback_str") and hasattr(pattern, "default_args")):
                continue

            for view in pattern.default_args.values():
                module_name = pattern._callback_str.replace(".rest_dispatch", "")
                self.check_function_exists(module_name, view)

    # Tests function-based views declared in urls.urlpatterns for
    # whether the function exists.  We at present do not test the
    # class-based views.
    def test_non_api_url_resolution(self):
        for pattern in urls.urlpatterns:
            if not hasattr(pattern, "_callback_str"):
                continue
            (module_name, base_view) = pattern._callback_str.rsplit(".", 1)
            self.check_function_exists(module_name, base_view)
