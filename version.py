import os

ZULIP_VERSION = "2.0.4+git"
# Add information on number of commits and commit hash to version, if available
zulip_git_version_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zulip-git-version')
if os.path.exists(zulip_git_version_file):
    with open(zulip_git_version_file) as f:
        version = f.read().strip()
        if version:
            ZULIP_VERSION = version

LATEST_MAJOR_VERSION = "2.0"
LATEST_RELEASE_VERSION = "2.0.4"
LATEST_RELEASE_ANNOUNCEMENT = "https://blog.zulip.org/2019/03/01/zulip-2-0-released/"

# Bump the minor PROVISION_VERSION to indicate that folks should provision
# only when going from an old version of the code to a newer version. Bump
# the major version to indicate that folks should provision in both
# directions.

# Typically,
# * adding a dependency only requires a minor version bump;
# * removing a dependency requires a major version bump;
# * upgrading a dependency requires a major version bump, unless the
#   upgraded dependency is backwards compatible with all of our
#   historical commits sharing the same major version, in which case a
#   minor version bump suffices.

PROVISION_VERSION = '54.0'
