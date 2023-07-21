import os
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

from zulint.custom_rules import RuleList

from tools.linter_lib.custom_check import non_py_rules, python_rules

ROOT_DIR = os.path.abspath(os.path.join(__file__, "..", "..", ".."))
CHECK_MESSAGE = "Fix the corresponding rule in `tools/linter_lib/custom_check.py`."


class TestRuleList(TestCase):
    def setUp(self) -> None:
        all_rules = list(python_rules.rules)
        for rule in non_py_rules:
            all_rules.extend(rule.rules)
        self.all_rules = all_rules

    def test_paths_in_rules(self) -> None:
        """Verifies that the paths mentioned in linter rules actually exist"""
        for rule in self.all_rules:
            for path in rule.get("exclude", {}):
                abs_path = os.path.abspath(os.path.join(ROOT_DIR, path))
                self.assertTrue(
                    os.path.exists(abs_path),
                    f"'{path}' is neither an existing file, nor a directory. {CHECK_MESSAGE}",
                )

            for line_tuple in rule.get("exclude_line", {}):
                path = line_tuple[0]
                abs_path = os.path.abspath(os.path.join(ROOT_DIR, path))
                self.assertTrue(
                    os.path.isfile(abs_path), f"The file '{path}' doesn't exist. {CHECK_MESSAGE}"
                )

            for path in rule.get("include_only", {}):
                if not os.path.splitext(path)[1]:
                    self.assertTrue(
                        path.endswith("/"),
                        f"The path '{path}' should end with '/'. {CHECK_MESSAGE}",
                    )

    def test_rule_patterns(self) -> None:
        """Verifies that the search regex specified in a custom rule actually matches
        the expectation and doesn't throw false positives."""
        for rule in self.all_rules:
            pattern = rule["pattern"]
            for line in rule.get("good_lines", []):
                with patch("builtins.open", return_value=StringIO(line + "\n\n"), autospec=True):
                    self.assertFalse(
                        RuleList([], [rule]).custom_check_file("foo.bar", "baz", ""),
                        f"The pattern '{pattern}' matched the line '{line}' while it shouldn't.",
                    )

            for line in rule.get("bad_lines", []):
                for filename in rule.get("include_only", {"foo.bar"}):
                    with patch(
                        "builtins.open", return_value=StringIO(line + "\n\n"), autospec=True
                    ), patch("builtins.print"):
                        self.assertTrue(
                            RuleList([], [rule]).custom_check_file(filename, "baz", ""),
                            f"The pattern '{pattern}' didn't match the line '{line}' while it should.",
                        )
