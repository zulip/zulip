from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.actions.mcp_tokens import do_create_mcp_api_token, do_revoke_mcp_api_token
from zerver.lib.exceptions import JsonableError, ResourceNotFoundError
from zerver.lib.response import json_success
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint, typed_endpoint_without_parameters
from zerver.models import UserProfile
from zerver.models.mcp import UserMCPApiToken


@typed_endpoint
def create_mcp_token(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    label: str,
) -> HttpResponse:
    if user_profile.is_bot:
        raise JsonableError(_("Bots cannot create MCP tokens."))
    if not label or len(label) > UserMCPApiToken.MAX_LABEL_LENGTH:
        raise JsonableError(_("Invalid token label."))
    if (
        UserMCPApiToken.objects.filter(user_profile=user_profile).count()
        >= UserMCPApiToken.MAX_TOKENS_PER_USER
    ):
        raise JsonableError(_("You already have the maximum number of MCP tokens."))

    token, raw_token = do_create_mcp_api_token(user_profile, label, acting_user=user_profile)
    return json_success(request, data={"id": token.id, "label": token.label, "token": raw_token})


@typed_endpoint_without_parameters
def list_mcp_tokens(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    tokens = UserMCPApiToken.objects.filter(user_profile=user_profile).order_by("date_created")
    return json_success(
        request,
        data={
            "tokens": [
                {
                    "id": token.id,
                    "label": token.label,
                    "date_created": datetime_to_timestamp(token.date_created),
                    "last_used": (
                        datetime_to_timestamp(token.last_used)
                        if token.last_used is not None
                        else None
                    ),
                }
                for token in tokens
            ]
        },
    )


@typed_endpoint
def delete_mcp_token(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    token_id: PathOnly[int],
) -> HttpResponse:
    try:
        token = UserMCPApiToken.objects.get(id=token_id, user_profile=user_profile)
    except UserMCPApiToken.DoesNotExist:
        raise ResourceNotFoundError(_("MCP token not found."))
    do_revoke_mcp_api_token(user_profile, token)
    return json_success(request)
