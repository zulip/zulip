from unittest import TestCase
from unittest.mock import patch
from  lib.test_script import find_js_test_files


class TestJSTestFiles(TestCase):
    def setUp(self) -> None:
        self.test_dir = "web/e2e-tests"
        self.mock_files = [
            'admin.test.ts',
            'compose.test.ts',
            'admin.ts',
            'settings.test.ts'
        ]

    def test_partial_match_resolution(self) -> None:
        """Tests that partial matches resolve to correct test files."""
        with patch('os.listdir', return_value=self.mock_files), \
             patch('os.path.isfile', side_effect=lambda x: x in self.mock_files):
            result = find_js_test_files(self.test_dir, ['admin'])
            self.assertEqual(
                len(result), 1,
                "Should find exactly one match for partial name"
            )
            self.assertEqual(
                result[0], 'admin.test.ts',
                "Should return 'admin.test.ts' as the matching file"
            )

    def test_non_test_file_error(self) -> None:
        """Tests error handling when attempting to run non-test files."""
        with patch('os.listdir', return_value=self.mock_files), \
             patch('os.path.isfile', side_effect=lambda x: x in self.mock_files):
            with self.assertRaises(Exception) as context:
                find_js_test_files(self.test_dir, ['admin.ts'])
            error_msg = str(context.exception)
            self.assertIn('admin.test.ts', error_msg)

    def test_missing_file_error(self) -> None:
        """Tests error handling for non-existent files."""
        with patch('os.listdir', return_value=self.mock_files), \
             patch('os.path.isfile', side_effect=lambda x: x in self.mock_files):
            with self.assertRaises(Exception) as context:
                find_js_test_files(self.test_dir, ['nonexistent'])
            self.assertIn('Cannot find a matching test file', str(context.exception))
