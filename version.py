# Includes information about how many commits the Zulip version is
# behind master.

import subprocess

command = "git log --pretty=oneline 2.0.2..HEAD | wc"
output = subprocess.getoutput("git log --pretty=oneline 2.0.2..HEAD | wc")

parts = [] # type: List[str]
parts = output.split()

ZULIP_VERSION = "2.0.2+git - "
ZULIP_VERSION += parts[0]
ZULIP_VERSION += " commits to master since this release"
LATEST_MAJOR_VERSION = "2.0"
LATEST_RELEASE_VERSION = "2.0.2"
LATEST_RELEASE_ANNOUNCEMENT = "https://blog.zulip.org/2019/03/01/zulip-2-0-released/"

# Bump the minor PROVISION_VERSION to indicate that folks should provision
# only when going from an old version of the code to a newer version. Bump
# the major version to indicate that folks should provision in both
# directions.

# Typically, adding a dependency only requires a minor version bump, and
# removing a dependency requires a major version bump.

PROVISION_VERSION = '30.2'
