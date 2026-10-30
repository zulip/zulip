from collections.abc import Callable
from typing import Any

from zerver.lib.github import get_github_issue_or_pr_data, url_not_previewable_error

# Maps a preview "platform" to the function that fetches its data, given the
# owner/repo/number that the Markdown renderer parsed out of the link and
# attached to the `previewable` anchor as data attributes. Each provider
# validates its own owner/repo/number, since the valid formats differ by
# platform. Adding another provider (e.g. GitLab) is a matter of adding an
# entry here.
LINK_PREVIEW_PROVIDERS: dict[str, Callable[[str, str, str], dict[str, Any]]] = {
    "github": get_github_issue_or_pr_data,
}


def get_link_preview_data(platform: str, owner: str, repo: str, number: str) -> dict[str, Any]:
    fetch = LINK_PREVIEW_PROVIDERS.get(platform)
    if fetch is None:
        raise url_not_previewable_error()
    return fetch(owner, repo, number)
