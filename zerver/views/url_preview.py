from django.http import HttpRequest, HttpResponse

from zerver.lib.link_preview import get_link_preview_data
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile


@typed_endpoint
def get_url_preview_data(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    platform: str,
    owner: str,
    repo: str,
    number: str,
) -> HttpResponse:
    return json_success(request, data=get_link_preview_data(platform, owner, repo, number))
