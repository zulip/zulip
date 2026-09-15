from collections.abc import Iterable

from django.db import transaction

from zerver.lib.alert_words import (
    WatchedPhraseData,
    WatchedPhraseDict,
    add_user_watched_phrases,
    remove_user_watched_phrases,
)
from zerver.models import UserProfile
from zerver.tornado.django_api import send_event_on_commit


def notify_watched_phrases(
    user_profile: UserProfile,
    watched_phrases: list[WatchedPhraseDict],
    *,
    phrases_changed: bool,
) -> None:
    event = dict(type="watched_phrases", watched_phrases=watched_phrases)
    send_event_on_commit(user_profile.realm, event, [user_profile.id])

    # Clients that haven't migrated to the `watched_phrases` API get the
    # legacy `alert_words` event. It can only express the set of phrases,
    # so it has nothing to say when only a phrase's configuration changed.
    if not phrases_changed:
        return

    legacy_event = dict(
        type="alert_words",
        alert_words=[phrase["watched_phrase"] for phrase in watched_phrases],
    )
    send_event_on_commit(user_profile.realm, legacy_event, [user_profile.id])


@transaction.atomic(durable=True)
def do_add_watched_phrases(
    user_profile: UserProfile, watched_phrases: Iterable[WatchedPhraseData]
) -> None:
    phrases, phrases_changed = add_user_watched_phrases(user_profile, watched_phrases)
    notify_watched_phrases(user_profile, phrases, phrases_changed=phrases_changed)


def do_add_alert_words(user_profile: UserProfile, alert_words: Iterable[str]) -> None:
    """Adds alert words without configuring them, for the legacy
    `alert_words` API and internal callers."""
    do_add_watched_phrases(
        user_profile, [WatchedPhraseData(watched_phrase=word) for word in alert_words]
    )


@transaction.atomic(durable=True)
def do_remove_watched_phrases(user_profile: UserProfile, watched_phrases: Iterable[str]) -> None:
    phrases, phrases_changed = remove_user_watched_phrases(user_profile, watched_phrases)
    notify_watched_phrases(user_profile, phrases, phrases_changed=phrases_changed)
