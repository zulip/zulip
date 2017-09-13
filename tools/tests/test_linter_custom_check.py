import os

from itertools import chain
from mock import patch
from unittest import TestCase

from typing import Any, Dict, List

from tools.linter_lib.custom_check import build_custom_checkers
from tools.linter_lib.custom_check import custom_check_file

ROOT_DIR = os.path.abspath(os.path.join(__file__, '..', '..', '..'))
CHECK_MESSAGE = "Fix the corresponding rule in `tools/linter_lib/custom_check.py`."

class TestCustomRules(TestCase):

    def setUp(self):
        # type: () -> None
        self.all_rules = []  # type: List[Dict[str, Any]]
        with patch('tools.linter_lib.custom_check.custom_check_file', return_value=False) as mock_custom_check_file:
            by_lang = dict.fromkeys(['py', 'js', 'sh', 'css', 'handlebars', 'html', 'json', 'md', 'txt', 'text', 'yaml'],
                                    ['foo/bar.baz'])
            check_custom_checks_py, check_custom_checks_nonpy = build_custom_checkers(by_lang)
            check_custom_checks_py()
            check_custom_checks_nonpy()
            for call_args in mock_custom_check_file.call_args_list:
                rule_set = call_args[0][2]
                self.all_rules.extend(rule_set)

    def test_paths_in_rules(self):
        # type: () -> None
        """Verifies that the paths mentioned in linter rules actually exist"""
        for rule in self.all_rules:
            for path in rule.get('exclude', {}):
                abs_path = os.path.abspath(os.path.join(ROOT_DIR, path))
                self.assertTrue(os.path.exists(abs_path),
                                "'{}' is neither an existing file, nor a directory. {}".format(path, CHECK_MESSAGE))

            for line_tuple in rule.get('exclude_line', {}):
                path = line_tuple[0]
                abs_path = os.path.abspath(os.path.join(ROOT_DIR, path))
                self.assertTrue(os.path.isfile(abs_path),
                                "The file '{}' doesn't exist. {}".format(path, CHECK_MESSAGE))

            for path in rule.get('include_only', {}):
                if not os.path.splitext(path)[1]:
                    self.assertTrue(path.endswith('/'),
                                    "The path '{}' should end with '/'. {}".format(path, CHECK_MESSAGE))

    def test_rule_patterns(self):
        # type: () -> None
        """Verifies that the search regex specified in a custom rule actually matches
           the expectation and doesn't throw false positives."""
        for rule in self.all_rules:
            pattern = rule['pattern']
            for line in rule.get('good_lines', []):
                # create=True is superfluous when mocking built-ins in Python >= 3.5
                with patch('builtins.open', return_value=iter((line+'\n\n').splitlines()), create=True, autospec=True):
                    self.assertFalse(custom_check_file('foo.bar', 'baz', [rule], ''),
                                     "The pattern '{}' matched the line '{}' while it shouldn't.".format(pattern, line))

            for line in rule.get('bad_lines', []):
                # create=True is superfluous when mocking built-ins in Python >= 3.5
                with patch('builtins.open',
                           return_value=iter((line+'\n\n').splitlines()), create=True, autospec=True), patch('builtins.print'):
                    self.assertTrue(custom_check_file('foo.bar', 'baz', [rule], ''),
                                    "The pattern '{}' didn't match the line '{}' while it should.".format(pattern, line))
