from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json

from zerver.actions.realm_linkifiers import (
    check_reorder_linkifiers,
    do_add_linkifier,
    do_remove_linkifier,
    do_update_linkifier,
)
from zerver.decorator import require_realm_admin
from zerver.lib.exceptions import JsonableError, ValidationFailureError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models import RealmFilter, UserProfile
from zerver.models.linkifiers import linkifiers_for_realm


# Custom realm linkifiers
def list_linkifiers(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    linkifiers = linkifiers_for_realm(user_profile.realm_id)
    return json_success(request, data={"linkifiers": linkifiers})


@require_realm_admin
@typed_endpoint
def create_linkifier(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    pattern: str,
    url_template: str,
) -> HttpResponse:
    try:
        linkifier_id = do_add_linkifier(
            realm=user_profile.realm,
            pattern=pattern,
            url_template=url_template,
            acting_user=user_profile,
        )
        return json_success(request, data={"id": linkifier_id})
    except ValidationError as e:
        raise ValidationFailureError(e)


@require_realm_admin
def delete_linkifier(
    request: HttpRequest, user_profile: UserProfile, filter_id: int
) -> HttpResponse:
    try:
        do_remove_linkifier(realm=user_profile.realm, id=filter_id, acting_user=None)
    except RealmFilter.DoesNotExist:
        raise JsonableError(_("Linkifier not found."))
    return json_success(request)


@require_realm_admin
@typed_endpoint
def update_linkifier(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    filter_id: PathOnly[int],
    pattern: str,
    url_template: str,
) -> HttpResponse:
    try:
        do_update_linkifier(
            realm=user_profile.realm,
            id=filter_id,
            pattern=pattern,
            url_template=url_template,
            acting_user=user_profile,
        )
        return json_success(request)
    except RealmFilter.DoesNotExist:
        raise JsonableError(_("Linkifier not found."))
    except ValidationError as e:
        raise ValidationFailureError(e)


@require_realm_admin
@typed_endpoint
def reorder_linkifiers(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    ordered_linkifier_ids: Json[list[int]],
) -> HttpResponse:
    check_reorder_linkifiers(user_profile.realm, ordered_linkifier_ids, acting_user=user_profile)
    return json_success(request)
