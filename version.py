import os

ZULIP_VERSION = "4.0-dev+git"
# Add information on number of commits and commit hash to version, if available
zulip_git_version_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zulip-git-version')
if os.path.exists(zulip_git_version_file):
    with open(zulip_git_version_file) as f:
        version = f.read().strip()
        if version:
            ZULIP_VERSION = version

LATEST_MAJOR_VERSION = "3.0"
LATEST_RELEASE_VERSION = "3.0"
LATEST_RELEASE_ANNOUNCEMENT = "https://blog.zulip.org/2020/07/16/zulip-3-0-released/"
LATEST_DESKTOP_VERSION = "5.4.0"

# Versions of the desktop app below DESKTOP_MINIMUM_VERSION will be
# prevented from connecting to the Zulip server.  Versions above
# DESKTOP_MINIMUM_VERSION but below DESKTOP_WARNING_VERSION will have
# a banner at the top of the page asking the user to upgrade.
DESKTOP_MINIMUM_VERSION = "5.0.0"
DESKTOP_WARNING_VERSION = "5.2.0"

# Bump the API_FEATURE_LEVEL whenever an API change is made
# that clients might want to condition on.  If we forget at
# the time we make the change, then bump it later as soon
# as we notice; clients using API_FEATURE_LEVEL will just not
# use the new feature/API until the bump.
#
# Changes should be accompanied by documentation explaining what the
# new level means in templates/zerver/api/changelog.md.
API_FEATURE_LEVEL = 30

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

PROVISION_VERSION = '97.1'
