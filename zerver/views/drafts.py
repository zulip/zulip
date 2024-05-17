from typing import List

from django.http import HttpRequest, HttpResponse
from pydantic import Json

from zerver.lib.drafts import (
    DraftData,
    do_create_drafts,
    do_delete_draft,
    do_edit_draft,
    draft_endpoint,
)
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models import Draft, UserProfile


@draft_endpoint
def fetch_drafts(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    user_drafts = Draft.objects.filter(user_profile=user_profile).order_by("last_edit_time")
    draft_dicts = [draft.to_dict() for draft in user_drafts]
    return json_success(request, data={"count": user_drafts.count(), "drafts": draft_dicts})


@draft_endpoint
@typed_endpoint
def create_drafts(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    drafts: Json[List[DraftData]],
) -> HttpResponse:
    created_draft_objects = do_create_drafts(drafts, user_profile)
    draft_ids = [draft_object.id for draft_object in created_draft_objects]
    return json_success(request, data={"ids": draft_ids})


@draft_endpoint
@typed_endpoint
def edit_draft(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    draft_id: PathOnly[int],
    draft: Json[DraftData],
) -> HttpResponse:
    do_edit_draft(draft_id, draft, user_profile)
    return json_success(request)


@draft_endpoint
def delete_draft(request: HttpRequest, user_profile: UserProfile, *, draft_id: int) -> HttpResponse:
    do_delete_draft(draft_id, user_profile)
    return json_success(request)
