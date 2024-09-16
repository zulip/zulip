import hashlib
import json
import logging
from typing import Any
from urllib.parse import urlparse

import requests
from django.conf import settings

from zerver.lib.cache import cache_with_key
from zerver.lib.outgoing_http import OutgoingSession

logger = logging.getLogger(__name__)

GITHUB_API_HOST = "https://api.github.com"


class GithubAPIException(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class GithubSession(OutgoingSession):
    def __init__(self, **kwargs: Any) -> None:
        github_api_auth_token = settings.GITHUB_API_AUTH_TOKEN
        headers = {}
        if github_api_auth_token is not None:
            headers = {"Authorization": f"token {github_api_auth_token}"}
        super().__init__(role="github", timeout=5, headers=headers, **kwargs)


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
        latest_version = latest_version.removeprefix("v")
        setup_file = PLATFORM_TO_SETUP_FILE[platform].format(version=latest_version)
        link = f"https://desktop-download.zulip.com/v{latest_version}/{setup_file}"
        if verify_release_download_link(link):
            return link
    return "https://github.com/zulip/zulip-desktop/releases/latest"


def parse_github_issue_url(url: str) -> dict[str, str] | None:
    try:
        parsed_url = urlparse(url)
        path_split = parsed_url.path.split("/")
        if (
            parsed_url.scheme.startswith("http")
            and parsed_url.hostname in ["www.github.com", "github.com"]
            and parsed_url.port is None
            and len(path_split) > 4
            and path_split[3] in ["issues", "pull"]
        ):
            return {
                "owner": path_split[1],
                "repo": path_split[2],
                "issue_number": path_split[4],
            }
        return None
    except Exception:
        return None


def get_issue_or_pr_cache_key(owner: str, repo: str, issue_number: str) -> str:
    github_api_auth_token = settings.GITHUB_API_AUTH_TOKEN
    if github_api_auth_token is not None:
        # We concatenate the hash with the key because the response contents from Github
        # also change accordingly. Therefore, if we update the key, we will immediately
        # start seeing limited responses that are only accessible with the new key.
        cache_key_hash = hashlib.sha256(github_api_auth_token.encode()).hexdigest()[:10]

        return f"github_issue_or_pr_data_{cache_key_hash}:{owner}/{repo}/{issue_number}"
    return f"github_issue_or_pr_data:{owner}/{repo}/{issue_number}"


@cache_with_key(get_issue_or_pr_cache_key, timeout=600)
def get_issue_or_pr_data(owner: str, repo: str, issue_number: str) -> dict[str, Any]:
    api_url = f"{GITHUB_API_HOST}/repos/{owner}/{repo}/issues/{issue_number}"
    try:
        response = GithubSession().get(api_url)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        response_data = {
            "type": "pull_request" if "pull_request" in data else "issue",
            "owner": owner,
            "repo": repo,
            "issue_number": issue_number,
            "title": data["title"],
            "author": data["user"]["login"],
            "state": data["state"],
        }
        if response_data["type"] == "issue":
            response_data["state_reason"] = data["state_reason"]
        if response_data["type"] == "pull_request":
            response_data["draft"] = data["draft"]
            response_data["merged_at"] = data["pull_request"]["merged_at"]
        return response_data
    except requests.RequestException as err:
        status_code = (
            err.response.status_code
            if hasattr(err, "response") and hasattr(err.response, "status_code")
            else None
        )
        raise GithubAPIException(str(err), status_code=status_code)
