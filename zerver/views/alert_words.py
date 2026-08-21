from typing import Annotated

from django.http import HttpRequest, HttpResponse
from pydantic import Json, StringConstraints

from zerver.actions.alert_words import (
    do_add_alert_words,
    do_add_watched_phrases,
    do_remove_watched_phrases,
)
from zerver.lib.alert_words import (
    MAX_ALERT_WORD_LENGTH,
    WatchedPhraseData,
    user_alert_words,
    user_watched_phrases,
)
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile


def list_alert_words(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success(request, data={"alert_words": user_alert_words(user_profile)})


def clean_alert_words(alert_words: list[str]) -> list[str]:
    alert_words = [w.strip() for w in alert_words]
    return [w for w in alert_words if w != ""]


def clean_watched_phrases(watched_phrases: list[WatchedPhraseData]) -> list[WatchedPhraseData]:
    for phrase in watched_phrases:
        phrase.watched_phrase = phrase.watched_phrase.strip()
    return [phrase for phrase in watched_phrases if phrase.watched_phrase != ""]


@typed_endpoint
def add_alert_words(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    alert_words: Json[list[Annotated[str, StringConstraints(max_length=MAX_ALERT_WORD_LENGTH)]]],
) -> HttpResponse:
    do_add_alert_words(user_profile, clean_alert_words(alert_words))
    return json_success(request, data={"alert_words": user_alert_words(user_profile)})


@typed_endpoint
def remove_alert_words(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    alert_words: Json[list[str]],
) -> HttpResponse:
    do_remove_watched_phrases(user_profile, alert_words)
    return json_success(request, data={"alert_words": user_alert_words(user_profile)})


def list_watched_phrases(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success(request, data={"watched_phrases": user_watched_phrases(user_profile)})


@typed_endpoint
def add_watched_phrases(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    watched_phrases: Json[list[WatchedPhraseData]],
) -> HttpResponse:
    do_add_watched_phrases(user_profile, clean_watched_phrases(watched_phrases))
    return json_success(request, data={"watched_phrases": user_watched_phrases(user_profile)})


@typed_endpoint
def remove_watched_phrases(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    watched_phrases: Json[list[str]],
) -> HttpResponse:
    do_remove_watched_phrases(user_profile, watched_phrases)
    return json_success(request, data={"watched_phrases": user_watched_phrases(user_profile)})
