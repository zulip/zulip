from unittest import TestCase, mock

from scripts.lib.run_hooks import maybe_resolve_version_string, resolve_version_string
from scripts.lib.zulip_tools import su_to_zulip

DEPLOY_PATH = "/var/lib/zulip"


class RunHooksTest(TestCase):
    def test_maybe_resolve_version_string_skips_missing_merge_bases(self) -> None:
        self.assertIsNone(maybe_resolve_version_string("", deploy_path=DEPLOY_PATH))
        self.assertIsNone(maybe_resolve_version_string("0.0.0", deploy_path=DEPLOY_PATH))

    @mock.patch("scripts.lib.run_hooks.subprocess.check_output", return_value="deadbeef\n")
    def test_resolve_version_string(self, check_output: mock.Mock) -> None:
        self.assertEqual(resolve_version_string("v1.2.3", deploy_path=DEPLOY_PATH), "deadbeef")
        check_output.assert_called_once_with(
            ["git", "rev-parse", "v1.2.3"],
            cwd=DEPLOY_PATH,
            preexec_fn=su_to_zulip,
            text=True,
        )

    @mock.patch("scripts.lib.run_hooks.resolve_version_string", return_value="deadbeef")
    def test_maybe_resolve_version_string_resolves_valid_versions(
        self, resolve_version_string_mock: mock.Mock
    ) -> None:
        self.assertEqual(
            maybe_resolve_version_string("v1.2.3", deploy_path=DEPLOY_PATH),
            "deadbeef",
        )
        resolve_version_string_mock.assert_called_once_with("v1.2.3", deploy_path=DEPLOY_PATH)
