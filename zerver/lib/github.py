import json
import logging
from typing import Any

import requests

from zerver.lib.cache import cache_with_key
from zerver.lib.outgoing_http import OutgoingSession

logger = logging.getLogger(__name__)


class GithubSession(OutgoingSession):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(role="github", timeout=5, **kwargs)


def get_latest_github_release_version_for_repo(repo: str) -> str:
    api_url = f"https://api.github.com/repos/zulip/{repo}/releases/latest"
    try:
        return GithubSession().get(api_url).json()["tag_name"]
    except (requests.RequestException, json.JSONDecodeError, KeyError):
        logger.exception(
            "Unable to fetch the latest release version from GitHub %s", api_url, stack_info=True
        )
        return ""


def verify_release_download_link(link: str) -> bool:
    try:
        GithubSession().head(link).raise_for_status()
        return True
    except requests.RequestException:
        logger.error("App download link is broken %s", link)
        return False


PLATFORM_TO_SETUP_FILE = {
    "linux": "Zulip-{version}-x86_64.AppImage",
    "mac": "Zulip-{version}-x64.dmg",
    "mac-arm64": "Zulip-{version}-arm64.dmg",
    "windows": "Zulip-Web-Setup-{version}.exe",
}


class InvalidPlatformError(Exception):
    pass


@cache_with_key(lambda platform: f"download_link:{platform}", timeout=60 * 30)
def get_latest_github_release_download_link_for_platform(platform: str) -> str:
    if platform not in PLATFORM_TO_SETUP_FILE:
        raise InvalidPlatformError

    latest_version = get_latest_github_release_version_for_repo("zulip-desktop")
    if latest_version:
        if latest_version[0] in ["v", "V"]:
            latest_version = latest_version[1:]
        setup_file = PLATFORM_TO_SETUP_FILE[platform].format(version=latest_version)
        link = f"https://desktop-download.zulip.com/v{latest_version}/{setup_file}"
        if verify_release_download_link(link):
            return link
    return "https://github.com/zulip/zulip-desktop/releases/latest"
