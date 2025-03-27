import requests
import responses

from zerver.lib.cache import cache_delete
from zerver.lib.github import (
    InvalidPlatformError,
    get_latest_github_release_download_link_for_platform,
)
from zerver.lib.test_classes import ZulipTestCase

logger_string = "zerver.lib.github"


class GitHubTestCase(ZulipTestCase):
    @responses.activate
    def test_get_latest_github_release_download_link_for_platform(self) -> None:
        responses.add(
            responses.GET,
            "https://api.github.com/repos/zulip/zulip-desktop/releases/latest",
            json={"tag_name": "v5.4.3"},
            status=200,
        )

        responses.add(
            responses.HEAD,
            "https://desktop-download.zulip.com/v5.4.3/Zulip-Web-Setup-5.4.3.exe",
            status=302,
        )
        self.assertEqual(
            get_latest_github_release_download_link_for_platform("windows"),
            "https://desktop-download.zulip.com/v5.4.3/Zulip-Web-Setup-5.4.3.exe",
        )

        responses.add(
            responses.HEAD,
            "https://desktop-download.zulip.com/v5.4.3/Zulip-5.4.3-x86_64.AppImage",
            status=302,
        )
        self.assertEqual(
            get_latest_github_release_download_link_for_platform("linux"),
            "https://desktop-download.zulip.com/v5.4.3/Zulip-5.4.3-x86_64.AppImage",
        )

        responses.add(
            responses.HEAD,
            "https://desktop-download.zulip.com/v5.4.3/Zulip-5.4.3-arm64.dmg",
            status=302,
        )
        self.assertEqual(
            get_latest_github_release_download_link_for_platform("mac"),
            "https://desktop-download.zulip.com/v5.4.3/Zulip-5.4.3-arm64.dmg",
        )

        responses.add(
            responses.HEAD,
            "https://desktop-download.zulip.com/v5.4.3/Zulip-5.4.3-arm64.dmg",
            status=302,
        )
        self.assertEqual(
            get_latest_github_release_download_link_for_platform("mac-arm64"),
            "https://desktop-download.zulip.com/v5.4.3/Zulip-5.4.3-arm64.dmg",
        )

        responses.add(
            responses.HEAD,
            "https://desktop-download.zulip.com/v5.4.3/Zulip-5.4.3-x64.dmg",
            status=302,
        )
        self.assertEqual(
            get_latest_github_release_download_link_for_platform("mac-intel"),
            "https://desktop-download.zulip.com/v5.4.3/Zulip-5.4.3-x64.dmg",
        )

        api_url = "https://api.github.com/repos/zulip/zulip-desktop/releases/latest"
        responses.replace(responses.GET, api_url, body=requests.RequestException())
        cache_delete("download_link:windows")
        with self.assertLogs(logger_string, level="ERROR") as error_log:
            self.assertEqual(
                get_latest_github_release_download_link_for_platform("windows"),
                "https://github.com/zulip/zulip-desktop/releases/latest",
            )
            self.assertIn(
                f"ERROR:{logger_string}:Unable to fetch the latest release version from GitHub {api_url}",
                error_log.output[0],
            )

        responses.replace(
            responses.GET,
            "https://api.github.com/repos/zulip/zulip-desktop/releases/latest",
            json={"tag_name": "5.4.4"},
            status=200,
        )
        download_link = "https://desktop-download.zulip.com/v5.4.4/Zulip-5.4.4-x86_64.AppImage"
        responses.add(responses.HEAD, download_link, status=404)
        cache_delete("download_link:linux")
        with self.assertLogs(logger_string, level="ERROR") as error_log:
            self.assertEqual(
                get_latest_github_release_download_link_for_platform("linux"),
                "https://github.com/zulip/zulip-desktop/releases/latest",
            )

            self.assertEqual(
                error_log.output,
                [f"ERROR:{logger_string}:App download link is broken {download_link}"],
            )

        with self.assertRaises(InvalidPlatformError):
            get_latest_github_release_download_link_for_platform("plan9")
