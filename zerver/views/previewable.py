import logging

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.lib.exceptions import ErrorCode, JsonableError
from zerver.lib.github import GithubAPIException, get_issue_or_pr_data, parse_github_issue_url
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import UserProfile

logger = logging.getLogger(__name__)


@has_request_variables
def get_previewable_data(
    request: HttpRequest, user_profile: UserProfile, url: str = REQ()
) -> HttpResponse:
    parsed_github_url = parse_github_issue_url(url)
    if parsed_github_url is not None:
        try:
            data = get_issue_or_pr_data(
                parsed_github_url["owner"],
                parsed_github_url["repo"],
                parsed_github_url["issue_number"],
            )
            response = {
                "platform": "github",
                "data": data
            }
            return json_success(request, response)
        except GithubAPIException as ex:
            if ex.status_code == 404:
                raise JsonableError(_("Invalid or expired URL."))
            else:
                if ex.status_code in [401, 402, 429]:
                    logger.warning("Error fetching issue data from GitHub: %s", ex)
                raise JsonableError(_("Unable to fetch data from github."))
    err = JsonableError(_("URL is not previewable."))
    err.code = ErrorCode.REQUEST_VARIABLE_INVALID
    raise err
