import os
from collections.abc import Sized
from unittest import TestCase
from unittest.mock import patch

from typing_extensions import override

from tools.lib.test_script import find_js_test_files


class TestJSTestFiles(TestCase):
    """Unit tests for JavaScript/TypeScript test file matching logic."""

    @override
    def setUp(self) -> None:
        """Setup mock test directory and files."""
        self.test_dir = "web/e2e-tests"
        self.mock_files = ["admin.test.ts", "compose.test.ts", "admin.ts", "settings.test.ts"]

    def assert_length(self, items: Sized, expected_length: int, msg: str | None = None) -> None:
        """Helper method to assert length of a sized object."""
        actual_length = len(items)
        if actual_length != expected_length:
            standardMsg = f"Length is {actual_length}, expected {expected_length}"
            msg = self._formatMessage(msg, standardMsg)
            raise self.failureException(msg)

    def test_partial_match_resolution(self) -> None:
        """Ensure partial matches return the correct test file."""
        with (
            patch("os.listdir", return_value=self.mock_files),
            patch("os.path.isfile", side_effect=lambda x: os.path.basename(x) in self.mock_files),
        ):
            result = find_js_test_files(self.test_dir, ["admin"])
            self.assert_length(result, 1, "Should find exactly one match for partial name")
            self.assertEqual(
                os.path.basename(result[0]),
                "admin.test.ts",
                "Should return 'admin.test.ts' as the matching file",
            )

    def test_non_test_file_error(self) -> None:
        """Ensure an exception is raised for non-test files."""
        with (
            patch("os.listdir", return_value=["compose.test.ts", "admin.ts", "settings.test.ts"]),
            patch("os.path.isfile", side_effect=lambda x: os.path.basename(x) in self.mock_files),
        ):
            with self.assertRaises(Exception) as context:
                find_js_test_files(self.test_dir, ["admin.ts"])
            error_msg = str(context.exception)
            self.assertIn("'admin.ts' is not a valid test file. Test files must end with '.test.ts' or '.test.js'", error_msg)

    def test_missing_file_error(self) -> None:
        """Ensure an exception is raised for missing files."""
        with (
            patch("os.listdir", return_value=self.mock_files),
            patch("os.path.isfile", side_effect=lambda x: os.path.basename(x) in self.mock_files),
        ):
            with self.assertRaises(Exception) as context:
                find_js_test_files(self.test_dir, ["nonexistent"])
            self.assertIn("Cannot find a matching test file", str(context.exception))
