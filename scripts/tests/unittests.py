# scripts library
import configparser
import datetime
import os

# unit testing library
import unittest
from unittest.mock import patch

# methods to be tested
from scripts.lib.zulip_tools import (
    get_deployment_version,
    make_deploy_path,
    is_invalid_upgrade,
    get_environment,
    get_config
    )

# Data
DEPLOYMENTS_DIR = "/home/zulip/deployments"
LOCK_DIR = os.path.join(DEPLOYMENTS_DIR, "lock")
TIMESTAMP_FORMAT = "%Y-%m-%d-%H-%M-%S"
TEMPLATE_DATABASE_DIR = "test-backend/databases"


# Color codes
OKBLUE = "\033[94m"
OKGREEN = "\033[92m"
WARNING = "\033[93m"
FAIL = "\033[91m"
ENDC = "\033[0m"
BLACKONYELLOW = "\x1b[0;30;43m"
WHITEONRED = "\x1b[0;37;41m"
BOLDRED = "\x1B[1;31m"
BOLD = "\x1b[1m"
GRAY = "\x1b[90m"

GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
BLUE = "\x1b[34m"
MAGENTA = "\x1b[35m"
CYAN = "\x1b[36m"


# get_deployment_version tests
@patch('os.listdir')
def test_default_version(self, mock_listdir):
    """ Test if the default version is returned when no matching items are
     found """

    # in fucntion, the version is initialized to "0.0.0" so empty should
    # return 0.0.0
    mock_listdir.return_value = []

    version = get_deployment_version("/fake/path")
    self.assertEqual(version, "0.0.0")


# make_deploy_path tests
def test_path_format(self):
    """ Test if the path is correctly formatted """

    path = make_deploy_path()
    self.assertTrue(path.startswith(DEPLOYMENTS_DIR))
    self.assertIn('/', path)


def test_timestamp_format(self):
    """ Test if the timestamp in the path matches the defined format """
    path = make_deploy_path()
    timestamp = path.split('/')[-1]
    try:
        datetime.datetime.strptime(timestamp, TIMESTAMP_FORMAT)
    except ValueError:
        self.fail("Timestamp format is incorrect")


# is_invalid_upgrade tests
def test_valid_upgrade(self):
    """ Test cases where the upgrade is valid """
    self.assertFalse(is_invalid_upgrade("1.3.10", "1.4.3"))
    self.assertFalse(is_invalid_upgrade("1.3.9", "1.4.2"))
    self.assertFalse(is_invalid_upgrade("1.4.4", "1.4.5"))


def test_invalid_upgrade(self):
    """ Test cases where the upgrade is invalid """
    self.assertTrue(is_invalid_upgrade("1.3.10", "1.4.4"))
    self.assertTrue(is_invalid_upgrade("1.3.9", "1.4.4"))


def test_bounds(self):
    """ Test boundary conditions """
    self.assertFalse(is_invalid_upgrade("1.3.10", "1.4.3"))
    self.assertTrue(is_invalid_upgrade("1.3.10", "1.4.4"))
    self.assertFalse(is_invalid_upgrade("1.4.3", "1.4.4"))


# get_environment test
@patch('os.path.exists')
def test_dir_exists(self, mock_exists):
    """ Test if the function returns 'prod' when DEPLOYMENTS_DIR exists """
    mock_exists.return_value = True
    self.assertEqual(get_environment(), "prod")


@patch('os.path.exists')
def test_dir_not_exist(self, mock_exists):
    """ Test if the function returns 'dev' when
    DEPLOYMENTS_DIR does not exist """
    mock_exists.return_value = False
    self.assertEqual(get_environment(), "dev")


# get_config tests
class TestGetConfig(unittest.TestCase):

    def setUp(self):
        # Setup config parser with some values
        self.config = configparser.RawConfigParser()
        self.config.add_section('TestSection')
        self.config.set('TestSection', 'existing_key', 'value')

    def test_key_found(self):
        """ Test if the correct value is returned for an existing key """
        value = get_config(self.config, 'TestSection', 'existing_key')
        self.assertEqual(value, 'value')

    def test_key_not_found_with_default(self):
        """ Test if the default value is returned when the key is not found """
        default = 'default_value'
        value = get_config(self.config, 'TestSection', 'non_existing_key',
                           default)
        self.assertEqual(value, default)

    def test_key_not_found_without_default(self):
        """ Test if an empty string is returned when the key is not
        found and no default is provided """
        value = get_config(self.config, 'TestSection', 'non_existing_key')
        self.assertEqual(value, '')


if __name__ == '__main__':
    unittest.main()
