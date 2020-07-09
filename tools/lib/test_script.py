import glob
import os
import subprocess
import sys
from distutils.version import LooseVersion
from typing import Iterable, List, Optional, Tuple

from scripts.lib.zulip_tools import get_dev_uuid_var_path
from version import PROVISION_VERSION

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_major_version(v: str) -> int:
    return int(v.split('.')[0])

def get_version_file() -> str:
    uuid_var_path = get_dev_uuid_var_path()
    return os.path.join(uuid_var_path, 'provision_version')

PREAMBLE = '''
Before we run tests, we make sure your provisioning version
is correct by looking at var/provision_version, which is at
version {}, and we compare it to the version in source
control (version.py), which is {}.
'''

def preamble(version: str) -> str:
    text = PREAMBLE.format(version, PROVISION_VERSION)
    text += '\n'
    return text

NEED_TO_DOWNGRADE = '''
It looks like you checked out a branch that expects an older
version of dependencies than the version you provisioned last.
This may be ok, but it's likely that you either want to rebase
your branch on top of upstream/master or re-provision your VM.

Do this: `./tools/provision`
'''

NEED_TO_UPGRADE = '''
It looks like you checked out a branch that has added
dependencies beyond what you last provisioned. Your command
is likely to fail until you add dependencies by provisioning.

Do this: `./tools/provision`
'''

def get_provisioning_status() -> Tuple[bool, Optional[str]]:
    version_file = get_version_file()
    if not os.path.exists(version_file):
        # If the developer doesn't have a version_file written by
        # a previous provision, then we don't do any safety checks
        # here on the assumption that the developer is managing
        # their own dependencies and not running provision.
        return True, None

    with open(version_file) as f:
        version = f.read().strip()

    # Normal path for people that provision--we're all good!
    if version == PROVISION_VERSION:
        return True, None

    # We may be more provisioned than the branch we just moved to.  As
    # long as the major version hasn't changed, then we should be ok.
    if LooseVersion(version) > LooseVersion(PROVISION_VERSION):
        if get_major_version(version) == get_major_version(PROVISION_VERSION):
            return True, None
        else:
            return False, preamble(version) + NEED_TO_DOWNGRADE

    return False, preamble(version) + NEED_TO_UPGRADE


def assert_provisioning_status_ok(force: bool) -> None:
    if not force:
        ok, msg = get_provisioning_status()
        if not ok:
            print(msg)
            print('If you really know what you are doing, use --force to run anyway.')
            sys.exit(1)


def find_js_test_files(test_dir: str, files: Iterable[str]) -> List[str]:
    test_files = []
    for file in files:
        for file_name in os.listdir(test_dir):
            if file_name.startswith(file):
                file = file_name
                break
        if not os.path.exists(file):
            file = os.path.join(test_dir, file)
        test_files.append(os.path.abspath(file))

    if not test_files:
        test_files = sorted(glob.glob(os.path.join(test_dir, '*.js')))

    return test_files

def prepare_puppeteer_run() -> None:
    os.chdir(ZULIP_PATH)
    subprocess.check_call(['node', 'node_modules/puppeteer/install.js'])
    os.makedirs('var/puppeteer', exist_ok=True)
    for f in glob.glob('var/puppeteer/puppeteer-failure*.png'):
        os.remove(f)
