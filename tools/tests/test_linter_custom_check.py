import os

from itertools import chain
from mock import patch, MagicMock
from unittest import TestCase

from tools.linter_lib.custom_check import build_custom_checkers

ROOT_DIR = os.path.abspath(os.path.join(__file__, '..', '..', '..'))
CHECK_MESSAGE = "Fix the corresponding rule in `tools/linter_lib/custom_check.py`."

@patch('tools.linter_lib.custom_check.custom_check_file', return_value=False)
class TestCustomRulesFormat(TestCase):
    def test_paths_in_rules(self, mock_custom_check_file):
        # type: (MagicMock) -> None
        """Verifies that the paths mentoned in linter rules actually exist"""
        by_lang = dict.fromkeys(['py', 'js', 'sh', 'css', 'handlebars', 'html', 'json', 'md', 'txt', 'text', 'yaml'],
                                ['foo/bar.baz'])
        check_custom_checks_py, check_custom_checks_nonpy = build_custom_checkers(by_lang)
        check_custom_checks_py()
        check_custom_checks_nonpy()
        for call_args in mock_custom_check_file.call_args_list:
            rule_set = call_args[0][2]
            for rule in rule_set:
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
