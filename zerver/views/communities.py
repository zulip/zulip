from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_safe

from zerver.lib.portico import get_public_realms_that_want_to_be_advertised
from zerver.lib.response import json_success


@require_safe
@csrf_exempt
def communities_api_view(
    request: HttpRequest,
) -> HttpResponse:
    eligible_realms, _ = get_public_realms_that_want_to_be_advertised()
    return json_success(request, data={"realms": eligible_realms})


@require_safe
@csrf_exempt
def communities_orgtypes_api_view(
    request: HttpRequest,
) -> HttpResponse:
    _, org_types_dict = get_public_realms_that_want_to_be_advertised()
    org_types = [
        {
            "key": key,
            "id": info["id"],
            "name": info["name"],
        }
        for key, info in org_types_dict.items()
    ]
    return json_success(request, data={"org_types": org_types})
