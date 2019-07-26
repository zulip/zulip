import os

from mock import patch
from unittest import TestCase

from zulint.custom_rules import RuleList
from linter_lib.custom_check import python_rules, non_py_rules

ROOT_DIR = os.path.abspath(os.path.join(__file__, '..', '..', '..'))
CHECK_MESSAGE = "Fix the corresponding rule in `tools/linter_lib/custom_check.py`."

class TestRuleList(TestCase):

    def setUp(self) -> None:
        self.all_rules = python_rules.rules
        for rule in non_py_rules:
            self.all_rules.extend(rule.rules)

    def test_paths_in_rules(self) -> None:
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

    def test_rule_patterns(self) -> None:
        """Verifies that the search regex specified in a custom rule actually matches
           the expectation and doesn't throw false positives."""
        for rule in self.all_rules:
            pattern = rule['pattern']
            for line in rule.get('good_lines', []):
                # create=True is superfluous when mocking built-ins in Python >= 3.5
                with patch('builtins.open', return_value=iter((line+'\n\n').splitlines()), create=True, autospec=True):
                    self.assertFalse(RuleList([], [rule]).custom_check_file('foo.bar', 'baz', ''),
                                     "The pattern '{}' matched the line '{}' while it shouldn't.".format(pattern, line))

            for line in rule.get('bad_lines', []):
                # create=True is superfluous when mocking built-ins in Python >= 3.5
                with patch('builtins.open',
                           return_value=iter((line+'\n\n').splitlines()), create=True, autospec=True), patch('builtins.print'):
                    filename = list(rule.get('include_only', {'foo.bar'}))[0]
                    self.assertTrue(RuleList([], [rule]).custom_check_file(filename, 'baz', ''),
                                    "The pattern '{}' didn't match the line '{}' while it should.".format(pattern, line))
