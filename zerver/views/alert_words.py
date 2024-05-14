from typing import List

from django.http import HttpRequest, HttpResponse
from pydantic import Json, StringConstraints
from typing_extensions import Annotated

from zerver.actions.alert_words import do_add_watched_phrases, do_remove_watched_phrases
from zerver.lib.alert_words import WatchedPhraseData, user_alert_words, user_watched_phrases
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile


def list_alert_words(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success(request, data={"alert_words": user_alert_words(user_profile)})


def list_watched_phrases(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success(
        request, data={"watched_phrases": [w.dict() for w in user_watched_phrases(user_profile)]}
    )


def clean_watched_phrases(watched_phrases: List[WatchedPhraseData]) -> List[WatchedPhraseData]:
    watched_phrase_data = [
        WatchedPhraseData(watched_phrase=w.watched_phrase.strip()) for w in watched_phrases
    ]
    return [w for w in watched_phrase_data if w.watched_phrase != ""]


@typed_endpoint
def add_alert_words(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    alert_words: Json[List[Annotated[str, StringConstraints(max_length=100)]]],
) -> HttpResponse:
    watched_phrases = [
        WatchedPhraseData(watched_phrase=watched_phrase) for watched_phrase in alert_words
    ]
    do_add_watched_phrases(user_profile, clean_watched_phrases(watched_phrases))
    return json_success(request, data={"alert_words": user_alert_words(user_profile)})


@typed_endpoint
def add_watched_phrases(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    watched_phrases: Json[List[WatchedPhraseData]],
) -> HttpResponse:
    do_add_watched_phrases(user_profile, clean_watched_phrases(watched_phrases))
    return json_success(
        request, data={"watched_phrases": [w.dict() for w in user_watched_phrases(user_profile)]}
    )


@typed_endpoint
def remove_alert_words(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    alert_words: Json[List[str]],
) -> HttpResponse:
    do_remove_watched_phrases(user_profile, alert_words)
    return json_success(request, data={"alert_words": user_alert_words(user_profile)})


@typed_endpoint
def remove_watched_phrases(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    watched_phrases: Json[List[str]],
) -> HttpResponse:
    do_remove_watched_phrases(user_profile, watched_phrases)
    return json_success(
        request, data={"watched_phrases": [w.dict() for w in user_watched_phrases(user_profile)]}
    )
