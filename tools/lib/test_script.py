from typing import Optional, Tuple

import os
from distutils.version import LooseVersion
from version import PROVISION_VERSION
from scripts.lib.zulip_tools import get_dev_uuid_var_path

def get_major_version(v):
    # type: (str) -> int
    return int(v.split('.')[0])

def get_version_file():
    # type: () -> str
    uuid_var_path = get_dev_uuid_var_path()
    return os.path.join(uuid_var_path, 'provision_version')

PREAMBLE = '''
Before we run tests, we make sure your provisioning version
is correct by looking at var/provision_version, which is at
version %s, and we compare it to the version in source
control (version.py), which is %s.
'''

def preamble(version):
    # type: (str) -> str
    text = PREAMBLE % (version, PROVISION_VERSION)
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

def get_provisioning_status():
    # type: () -> Tuple[bool, Optional[str]]

    version_file = get_version_file()
    if not os.path.exists(version_file):
        # If the developer doesn't have a version_file written by
        # a previous provision, then we don't do any safety checks
        # here on the assumption that the developer is managing
        # their own dependencies and not running provision.
        return True, None

    version = open(version_file).read().strip()

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
