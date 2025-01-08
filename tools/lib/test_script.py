import glob
import os
import subprocess
import sys
from argparse import ArgumentParser
from collections.abc import Iterable

from scripts.lib.zulip_tools import get_dev_uuid_var_path
from version import PROVISION_VERSION

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_version_file() -> str:
    uuid_var_path = get_dev_uuid_var_path()
    return os.path.join(uuid_var_path, "provision_version")


PREAMBLE = """
Provisioning state check failed! This check compares
`var/provision_version` (currently {}) to the version in
source control (`version.py`), which is {}, to see if you
likely need to provision before this command can run
properly.
"""


def preamble(version: tuple[int, ...]) -> str:
    text = PREAMBLE.format(version, PROVISION_VERSION)
    text += "\n"
    return text


NEED_TO_DOWNGRADE = """
The branch you are currently on expects an older version of
dependencies than the version you provisioned last. This may
be ok, but it's likely that you either want to rebase your
branch on top of upstream/main or re-provision your machine.

Do this: `./tools/provision`
"""

NEED_TO_UPGRADE = """
The branch you are currently on has added dependencies beyond
what you last provisioned. Your command is likely to fail
until you add dependencies by provisioning.

Do this: `./tools/provision`
"""


def get_provisioning_status() -> tuple[bool, str | None]:
    version_file = get_version_file()
    if not os.path.exists(version_file):
        # If the developer doesn't have a version_file written by
        # a previous provision, then we don't do any safety checks
        # here on the assumption that the developer is managing
        # their own dependencies and not running provision.
        return True, None

    with open(version_file) as f:
        version = tuple(map(int, f.read().strip().split(".")))

    # We may be more provisioned than the branch we just moved to.  As
    # long as the major version hasn't changed, then we should be ok.
    if version < PROVISION_VERSION:
        return False, preamble(version) + NEED_TO_UPGRADE
    elif version < (PROVISION_VERSION[0] + 1,):
        return True, None
    else:
        return False, preamble(version) + NEED_TO_DOWNGRADE


def assert_provisioning_status_ok(skip_provision_check: bool) -> None:
    if not skip_provision_check:
        ok, msg = get_provisioning_status()
        if not ok:
            print(msg)
            print(
                "If you really know what you are doing, use --skip-provision-check to run anyway."
            )
            sys.exit(1)


def add_provision_check_override_param(parser: ArgumentParser) -> None:
    """
    Registers --skip-provision-check argument to be used with various commands/tests in our tools.
    """
    parser.add_argument(
        "--skip-provision-check",
        action="store_true",
        help="Skip check that provision has been run; useful to save time if you know the dependency changes are not relevant to this command and will not cause it to fail",
    )


def find_js_test_files(test_dir: str, files: Iterable[str]) -> list[str]:
    """
    Find test files in the test directory with improved matching and error handling.
    Supports both direct matches and partial names, with special handling for test files.

    Args:
        test_dir: Directory containing test files
        files: Iterable of file names or patterns to match

    Returns:
        list[str]: List of absolute paths to matching test files

    Raises:
        Exception: If no matching test files are found with helpful suggestion message
    """
    test_files: list[str] = []
    available_files = os.listdir(test_dir)

    for file in files:
        # Remove extension if provided
        base_name = os.path.splitext(file)[0]

        # Find all possible matches
        matches = [
            f
            for f in available_files
            if f.startswith(base_name) and f.endswith((".test.ts", ".test.js"))
        ]

        # If no test file matches found, look for similar files for error message
        if not matches:
            similar_files = [
                f
                for f in available_files
                if f.startswith(base_name) or f.endswith((".test.ts", ".test.js"))
            ]

            error_msg = f"Cannot find a matching test file for '{file}' in '{test_dir}'"
            if similar_files:
                error_msg += "\nDid you mean one of these?\n" + "\n".join(
                    f"- {f}" for f in similar_files if f.endswith((".test.ts", ".test.js"))
                )
                if any(f == base_name + ".ts" or f == base_name + ".js" for f in similar_files):
                    error_msg += f"\n\nNote: '{base_name}.ts' is not a test file. Test files should end with '.test.ts'"
            raise Exception(error_msg)

        # Add absolute path of matching file
        test_files.extend(os.path.abspath(os.path.join(test_dir, match)) for match in matches)

    # If no files specified, return all test files
    if not test_files:
        test_files = sorted(
            glob.glob(os.path.join(test_dir, "*.test.ts"))
            + glob.glob(os.path.join(test_dir, "*.test.js"))
        )

    return test_files


def prepare_puppeteer_run(is_firefox: bool = False) -> None:
    os.chdir(ZULIP_PATH)
    # This will determine if the browser will be firefox or chrome.
    os.environ["PUPPETEER_PRODUCT"] = "firefox" if is_firefox else "chrome"
    subprocess.check_call(["node", "install.mjs"], cwd="node_modules/puppeteer")
    os.makedirs("var/puppeteer", exist_ok=True)
    for f in glob.glob("var/puppeteer/failure-*.png"):
        os.remove(f)
