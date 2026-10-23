import hashlib
import json
import logging
import re
from typing import Any
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.utils.translation import gettext as _

from zerver.lib.cache import cache_with_key
from zerver.lib.exceptions import ErrorCode, JsonableError
from zerver.lib.outgoing_http import OutgoingSession

logger = logging.getLogger(__name__)

GITHUB_HOSTNAMES = ("github.com", "www.github.com")


class GithubSession(OutgoingSession):
    def __init__(self, **kwargs: Any) -> None:
        # When configured, GITHUB_API_AUTH_TOKEN raises GitHub's API rate
        # limit from 60 to 5000 requests/hour. It is intended to authorize
        # access to public data only; see
        # docs/production/github-link-previews.md.
        headers = {}
        if settings.GITHUB_API_AUTH_TOKEN is not None:
            headers["Authorization"] = f"Bearer {settings.GITHUB_API_AUTH_TOKEN}"
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
    "mac": "Zulip-{version}-arm64.dmg",
    "mac-intel": "Zulip-{version}-x64.dmg",
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


def match_github_issue_or_pr_url(url: str) -> dict[str, str] | None:
    """If `url` points at a GitHub issue or pull request, return its owner,
    repo, and number; otherwise None. Used during Markdown rendering to tag
    previewable links.

    GitHub's REST API serves issues and pull requests from the same `issues`
    endpoint, so `/pull/N` and `/issues/N` are fetched identically -- which
    also means a `#123` org linkifier previews correctly whichever form it
    expands to.
    """
    try:
        split_url = urlsplit(url)
        port = split_url.port
    except ValueError:
        return None
    if split_url.hostname not in GITHUB_HOSTNAMES or port is not None:
        return None
    # Paths look like /{owner}/{repo}/(issues|pull)/{number}[/...].
    parts = split_url.path.split("/")
    if len(parts) < 5 or parts[3] not in ("issues", "pull") or not parts[4].isdigit():
        return None
    return {"owner": parts[1], "repo": parts[2], "number": parts[4]}


def github_issue_or_pr_cache_key(owner: str, repo: str, number: str) -> str:
    digest = hashlib.sha1(f"{owner}/{repo}/{number}".encode()).hexdigest()
    return f"github_issue_or_pr:{digest}"


def url_not_previewable_error() -> JsonableError:
    error = JsonableError(_("URL is not previewable."))
    error.code = ErrorCode.REQUEST_VARIABLE_INVALID
    return error


# GitHub's naming rules for these path segments, so a crafted owner/repo can't
# walk the upstream API path (`.`/`..`). Kept GitHub-specific since other
# platforms differ -- GitLab namespaces, for instance, may contain `/`.
GITHUB_OWNER_RE = re.compile(r"\A[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9]))*\Z")
GITHUB_REPO_RE = re.compile(r"\A[A-Za-z0-9._-]+\Z")


@cache_with_key(github_issue_or_pr_cache_key, timeout=60 * 10)
def fetch_github_issue_or_pr_data(owner: str, repo: str, number: str) -> dict[str, Any] | None:
    # Returns the preview data, or None if GitHub reports it doesn't exist
    # (404). None is cached too, so a repeatedly-hovered broken link doesn't
    # keep hitting the API; transient failures (rate limits, 5xx, network)
    # raise instead, so they aren't cached and recover as soon as GitHub does.
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"
    try:
        response = GithubSession().get(api_url)
        response.raise_for_status()
    except requests.RequestException as err:
        status_code = err.response.status_code if err.response is not None else None
        if status_code == 404:
            return None
        logger.warning("Unable to fetch GitHub preview data from %s: %s", api_url, err)
        raise JsonableError(_("Unable to fetch data from GitHub."))

    try:
        data: dict[str, Any] = response.json()
        is_pull_request = "pull_request" in data
        preview_data: dict[str, Any] = {
            "platform": "github",
            "type": "pull_request" if is_pull_request else "issue",
            "owner": owner,
            "repo": repo,
            "number": number,
            "title": data["title"],
            "author": data["user"]["login"],
            "state": data["state"],
        }
        if is_pull_request:
            preview_data["draft"] = data.get("draft", False)
            preview_data["merged_at"] = data["pull_request"].get("merged_at")
        else:
            preview_data["state_reason"] = data.get("state_reason")
    except (KeyError, TypeError, ValueError):
        # An unexpected 200 body (missing fields or non-JSON): degrade to a
        # fetch error rather than 500-ing.
        logger.warning("Unexpected GitHub preview response from %s", api_url)
        raise JsonableError(_("Unable to fetch data from GitHub."))
    return preview_data


def get_github_issue_or_pr_data(owner: str, repo: str, number: str) -> dict[str, Any]:
    if (
        GITHUB_OWNER_RE.match(owner) is None
        or GITHUB_REPO_RE.match(repo) is None
        or repo in (".", "..")
        or not number.isdigit()
    ):
        raise url_not_previewable_error()
    preview_data = fetch_github_issue_or_pr_data(owner, repo, number)
    if preview_data is None:
        # A cached-or-fresh negative result: GitHub has no such issue/PR.
        raise JsonableError(_("Invalid or expired URL."))
    return preview_data
