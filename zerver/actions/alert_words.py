from typing import Iterable, Sequence

from zerver.lib.alert_words import (
    WatchedPhraseData,
    add_user_watched_phrases,
    remove_user_watched_phrases,
)
from zerver.models import UserProfile
from zerver.tornado.django_api import send_event


def notify_watched_phrases(user_profile: UserProfile, phrases: Sequence[WatchedPhraseData]) -> None:
    event = dict(type="watched_phrases", watched_phrases=[w.dict() for w in phrases])
    send_event(user_profile.realm, event, [user_profile.id])
    event = dict(type="alert_words", alert_words=[phrase.watched_phrase for phrase in phrases])
    send_event(user_profile.realm, event, [user_profile.id])


def do_add_watched_phrases(
    user_profile: UserProfile, watched_phrases: Iterable[WatchedPhraseData]
) -> None:
    phrases = add_user_watched_phrases(user_profile, watched_phrases)
    notify_watched_phrases(user_profile, phrases)


def do_remove_watched_phrases(user_profile: UserProfile, watched_phrases: Iterable[str]) -> None:
    phrases = remove_user_watched_phrases(user_profile, watched_phrases)
    notify_watched_phrases(user_profile, phrases)
