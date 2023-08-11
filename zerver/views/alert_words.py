from typing import List

from django.http import HttpRequest, HttpResponse
from pydantic import Json, StringConstraints
from typing_extensions import Annotated

from zerver.actions.alert_words import do_add_alert_words, do_remove_alert_words
from zerver.lib.alert_words import user_alert_words
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile


def list_alert_words(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success(request, data={"alert_words": user_alert_words(user_profile)})


def clean_alert_words(alert_words: List[str]) -> List[str]:
    alert_words = [w.strip() for w in alert_words]
    return [w for w in alert_words if w != ""]


@typed_endpoint
def add_alert_words(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    alert_words: Json[List[Annotated[str, StringConstraints(max_length=100)]]],
) -> HttpResponse:
    do_add_alert_words(user_profile, clean_alert_words(alert_words))
    return json_success(request, data={"alert_words": user_alert_words(user_profile)})


@typed_endpoint
def remove_alert_words(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    alert_words: Json[List[str]],
) -> HttpResponse:
    do_remove_alert_words(user_profile, alert_words)
    return json_success(request, data={"alert_words": user_alert_words(user_profile)})
