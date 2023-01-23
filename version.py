import os

ZULIP_VERSION = "6.1"

# Add information on number of commits and commit hash to version, if available
zulip_git_version_file = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "zulip-git-version"
)
lines = [ZULIP_VERSION, ""]
if os.path.exists(zulip_git_version_file):
    with open(zulip_git_version_file) as f:
        lines = f.readlines() + ["", ""]
ZULIP_VERSION = lines.pop(0).strip()
ZULIP_MERGE_BASE = lines.pop(0).strip()

LATEST_MAJOR_VERSION = "6.0"
LATEST_RELEASE_VERSION = "6.1"
LATEST_RELEASE_ANNOUNCEMENT = "https://blog.zulip.com/2022/11/17/zulip-6-0-released/"

# Versions of the desktop app below DESKTOP_MINIMUM_VERSION will be
# prevented from connecting to the Zulip server.  Versions above
# DESKTOP_MINIMUM_VERSION but below DESKTOP_WARNING_VERSION will have
# a banner at the top of the page asking the user to upgrade.
DESKTOP_MINIMUM_VERSION = "5.2.0"
DESKTOP_WARNING_VERSION = "5.4.3"

# Bump the API_FEATURE_LEVEL whenever an API change is made
# that clients might want to condition on.  If we forget at
# the time we make the change, then bump it later as soon
# as we notice; clients using API_FEATURE_LEVEL will just not
# use the new feature/API until the bump.
#
# Changes should be accompanied by documentation explaining what the
# new level means in templates/zerver/api/changelog.md, as well as
# "**Changes**" entries in the endpoint's documentation in `zulip.yaml`.
API_FEATURE_LEVEL = 156

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

PROVISION_VERSION = (213, 0)
