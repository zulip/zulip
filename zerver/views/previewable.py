from urllib.parse import urlparse

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.lib.exceptions import ErrorCode, JsonableError
from zerver.lib.github import get_issue_or_pr_data
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import UserProfile


@has_request_variables
def get_previewable_data(
    request: HttpRequest, user_profile: UserProfile, url: str = REQ()
) -> HttpResponse:
    try:
        parsed_url = urlparse(url)
    except ValueError:
        raise JsonableError(_("URL is not valid."))
    path_split = parsed_url.path.split("/")
    if (
        parsed_url.scheme not in ["http", "https"]
        or parsed_url.hostname not in ["www.github.com", "github.com"]
        or parsed_url.port is not None
        or len(path_split) <= 4
        or path_split[3] not in ["issues", "pull"]
    ):
        err = JsonableError(_("URL is not previewable."))
        err.code = ErrorCode.REQUEST_VARIABLE_INVALID
        raise err

    data = get_issue_or_pr_data(
        owner=path_split[1],
        repo=path_split[2],
        issue_number=path_split[4],
    )
    if data["result"] != "success":
        if data["status_code"] == 404:
            raise JsonableError(_("Invalid or expired URL."))
        else:
            raise JsonableError(_("Unable to fetch data from github."))
    return json_success(request, data)
