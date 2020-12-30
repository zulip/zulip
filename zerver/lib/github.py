import json
import logging

import requests

from zerver.lib.cache import cache_with_key

logger = logging.getLogger(__name__)

def get_latest_github_release_version_for_repo(repo: str) -> str:
    api_url = f"https://api.github.com/repos/zulip/{repo}/releases/latest"
    try:
        return requests.get(api_url).json()["tag_name"]
    except (requests.RequestException, json.JSONDecodeError, KeyError):
        logger.error("Unable to fetch the latest release version from GitHub %s", api_url)
        return ""

def verify_release_download_link(link: str) -> bool:
    try:
        requests.head(link).raise_for_status()
        return True
    except requests.RequestException:
        logger.error("App download link is broken %s", link)
        return False

PLATFORM_TO_SETUP_FILE = {
    "linux": "Zulip-{version}-x86_64.AppImage",
    "mac": "Zulip-{version}.dmg",
    "windows": "Zulip-Web-Setup-{version}.exe",
}

class InvalidPlatform(Exception):
    pass

@cache_with_key(lambda platform: f"download_link:{platform}", timeout=60*30)
def get_latest_github_release_download_link_for_platform(platform: str) -> str:
    if platform not in PLATFORM_TO_SETUP_FILE:
        raise InvalidPlatform()

    latest_version = get_latest_github_release_version_for_repo("zulip-desktop")
    if latest_version:
        if latest_version[0] in ["v", "V"]:
            latest_version = latest_version[1:]
        setup_file = PLATFORM_TO_SETUP_FILE[platform].format(version=latest_version)
        link = f"https://github.com/zulip/zulip-desktop/releases/download/v{latest_version}/{setup_file}"
        if verify_release_download_link(link):
            return link
    return "https://github.com/zulip/zulip-desktop/releases/latest"
