import unittest
from unittest import mock

from scripts.lib.hash_reqs import expand_reqs, hash_deps
from tools.setup.setup_venvs import DEV_REQS_FILE


class TestHashCreation(unittest.TestCase):

    def test_diff_hash_for_diff_python_version(self) -> None:
        with mock.patch('scripts.lib.hash_reqs.python_version', return_value='Python 3.6.9'):
            deps = expand_reqs(DEV_REQS_FILE)
            hash1 = hash_deps(deps)

        with mock.patch('scripts.lib.hash_reqs.python_version', return_value='Python 3.6.9'):
            deps = expand_reqs(DEV_REQS_FILE)
            hash2 = hash_deps(deps)

        with mock.patch('scripts.lib.hash_reqs.python_version', return_value='Python 3.8.2'):
            deps = expand_reqs(DEV_REQS_FILE)
            hash3 = hash_deps(deps)

        assert hash1 == hash2
        assert hash1 != hash3
