from typing import Annotated

from django.http import HttpRequest, HttpResponse
from pydantic import BaseModel, Json, StringConstraints

from zerver.actions.alert_words import do_add_alert_words, do_remove_alert_words
from zerver.lib.alert_words import AlertWordData, user_alert_words
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile


class AlertWordDataRequest(BaseModel):
    word: Annotated[str, StringConstraints(max_length=100)]
    automatically_follow_topics: bool = False


def list_alert_words(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success(request, data={"alert_words": user_alert_words(user_profile)})


def clean_alert_words(alert_words: list[str | AlertWordDataRequest]) -> list[str | AlertWordData]:
    cleaned_alert_words: list[str | AlertWordData] = []

    for word in alert_words:
        if isinstance(word, str):
            stripped_word = word.strip()
            if stripped_word != "":
                cleaned_alert_words.append(stripped_word)
            continue

        stripped_word = word.word.strip()
        if stripped_word != "":
            cleaned_alert_words.append(
                {
                    "word": stripped_word,
                    "automatically_follow_topics": word.automatically_follow_topics,
                }
            )

    return cleaned_alert_words


@typed_endpoint
def add_alert_words(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    alert_words: Json[
        list[Annotated[str, StringConstraints(max_length=100)] | AlertWordDataRequest]
    ],
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
    do_remove_alert_words(user_profile, alert_words)
    return json_success(request, data={"alert_words": user_alert_words(user_profile)})
