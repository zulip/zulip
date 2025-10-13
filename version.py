import os

ZULIP_VERSION = "12.0-dev+git"

# Add information on number of commits and commit hash to version, if available
ZULIP_VERSION_WITHOUT_COMMIT = ZULIP_VERSION
zulip_git_version_file = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "zulip-git-version"
)
lines = [ZULIP_VERSION, ""]
if os.path.exists(zulip_git_version_file):
    with open(zulip_git_version_file) as f:
        lines = [*f, "", ""]
ZULIP_VERSION = lines.pop(0).strip()
ZULIP_MERGE_BASE = lines.pop(0).strip()

LATEST_MAJOR_VERSION = "11.0"
LATEST_RELEASE_VERSION = "11.5"
LATEST_RELEASE_ANNOUNCEMENT = "https://blog.zulip.com/zulip-server-11-0"

# Versions of the desktop app below DESKTOP_MINIMUM_VERSION will be
# prevented from connecting to the Zulip server.  Versions above
# DESKTOP_MINIMUM_VERSION but below DESKTOP_WARNING_VERSION will have
# a banner at the top of the page asking the user to upgrade.
DESKTOP_MINIMUM_VERSION = "5.4.3"
DESKTOP_WARNING_VERSION = "5.9.3"

# API_FEATURE_LEVEL is bumped exclusively by tools/merge-api-changelogs, run by
# maintainers when an API change is merged to the main branch. When writing an
# API change, you run `tools/create-api-changelog`, which creates a special API
# changelog file and unique random ID for you to use when documentating your API
# change. For full process, see:
# https://zulip.readthedocs.io/en/latest/documentation/api.html#step-by-step-guide
# Also available at docs/documentation/api.md.

API_FEATURE_LEVEL = 467

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

PROVISION_VERSION = (369, 2)  # bumped 2026-02-09 to add jdenticon
