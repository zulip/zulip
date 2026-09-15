from collections.abc import Iterable
from typing import Annotated, TypedDict

import ahocorasick
from django.db import transaction
from django.db.models.functions import Lower
from pydantic import BaseModel, ConfigDict, StringConstraints

from zerver.lib.cache import (
    cache_with_key,
    realm_alert_words_automaton_cache_key,
    realm_alert_words_cache_key,
)
from zerver.models import AlertWord, Realm, UserProfile
from zerver.models.alert_words import flush_realm_alert_words

MAX_ALERT_WORD_LENGTH = 100


class WatchedPhraseDict(TypedDict):
    """A watched phrase and its configuration, as sent to clients."""

    watched_phrase: str
    automatically_follow_topics: bool


class WatchedPhraseData(BaseModel):
    """A watched phrase to add, as accepted from clients."""

    model_config = ConfigDict(extra="forbid")

    watched_phrase: Annotated[str, StringConstraints(max_length=MAX_ALERT_WORD_LENGTH)]
    # `None` means "leave unchanged" for a phrase the user already has
    # configured, and `False` for a phrase being added.
    automatically_follow_topics: bool | None = None


@cache_with_key(lambda realm: realm_alert_words_cache_key(realm.id), timeout=3600 * 24)
def alert_words_in_realm(realm: Realm) -> dict[int, list[str]]:
    user_ids_and_words = AlertWord.objects.filter(realm=realm, user_profile__is_active=True).values(
        "user_profile_id", "word"
    )
    user_ids_with_words: dict[int, list[str]] = {}
    for id_and_word in user_ids_and_words:
        user_ids_with_words.setdefault(id_and_word["user_profile_id"], [])
        user_ids_with_words[id_and_word["user_profile_id"]].append(id_and_word["word"])
    return user_ids_with_words


@cache_with_key(lambda realm: realm_alert_words_automaton_cache_key(realm.id), timeout=3600 * 24)
def get_alert_word_automaton(realm: Realm) -> ahocorasick.Automaton:
    user_id_with_words = alert_words_in_realm(realm)
    alert_word_automaton = ahocorasick.Automaton()
    for user_id, alert_words in user_id_with_words.items():
        for alert_word in alert_words:
            alert_word_lower = alert_word.lower()
            if alert_word_automaton.exists(alert_word_lower):
                (_key, user_ids_for_alert_word) = alert_word_automaton.get(alert_word_lower)
                user_ids_for_alert_word.add(user_id)
            else:
                alert_word_automaton.add_word(alert_word_lower, (alert_word_lower, {user_id}))
    alert_word_automaton.make_automaton()
    # If the kind is not AHOCORASICK after calling make_automaton, it means there is no key present
    # and hence we cannot call items on the automaton yet. To avoid it we return None for such cases
    # where there is no alert-words in the realm.
    # https://pyahocorasick.readthedocs.io/en/latest/#make-automaton
    if alert_word_automaton.kind != ahocorasick.AHOCORASICK:
        return None
    return alert_word_automaton


def user_alert_words(user_profile: UserProfile) -> list[str]:
    return list(AlertWord.objects.filter(user_profile=user_profile).values_list("word", flat=True))


def user_watched_phrases(user_profile: UserProfile) -> list[WatchedPhraseDict]:
    return [
        WatchedPhraseDict(
            watched_phrase=row["word"],
            automatically_follow_topics=row["automatically_follow_topics"],
        )
        for row in AlertWord.objects.filter(user_profile=user_profile).values(
            "word", "automatically_follow_topics"
        )
    ]


@transaction.atomic(savepoint=False)
def add_user_watched_phrases(
    user_profile: UserProfile, new_phrases: Iterable[WatchedPhraseData]
) -> tuple[list[WatchedPhraseDict], bool]:
    """Returns the user's watched phrases after the change, along with
    whether the set of phrases itself changed, as opposed to only the
    configuration of phrases the user already had."""
    existing_words = {
        alert_word.word.lower(): alert_word
        for alert_word in AlertWord.objects.filter(user_profile=user_profile)
    }

    # Keeping the case, use a dictionary to get the set of
    # case-insensitive distinct, new alert words
    word_dict: dict[str, WatchedPhraseData] = {}
    # Keyed by row so that a later entry for a phrase the user already
    # has overrides an earlier one, rather than asking bulk_update to
    # set the same row twice.
    new_configuration: dict[int, tuple[AlertWord, bool]] = {}
    for phrase in new_phrases:
        existing_word = existing_words.get(phrase.watched_phrase.lower())
        if existing_word is None:
            word_dict[phrase.watched_phrase.lower()] = phrase
        elif phrase.automatically_follow_topics is not None:
            new_configuration[existing_word.id] = (
                existing_word,
                phrase.automatically_follow_topics,
            )

    words_to_update: list[AlertWord] = []
    for alert_word, automatically_follow_topics in new_configuration.values():
        if alert_word.automatically_follow_topics != automatically_follow_topics:
            alert_word.automatically_follow_topics = automatically_follow_topics
            words_to_update.append(alert_word)

    AlertWord.objects.bulk_update(words_to_update, ["automatically_follow_topics"])
    AlertWord.objects.bulk_create(
        AlertWord(
            user_profile=user_profile,
            word=phrase.watched_phrase,
            realm=user_profile.realm,
            automatically_follow_topics=bool(phrase.automatically_follow_topics),
        )
        for phrase in word_dict.values()
    )
    # Django bulk_create and bulk_update operations don't flush caches,
    # so we need to do this ourselves.
    flush_realm_alert_words(user_profile.realm_id)

    return user_watched_phrases(user_profile), len(word_dict) > 0


@transaction.atomic(savepoint=False)
def remove_user_watched_phrases(
    user_profile: UserProfile, delete_words: Iterable[str]
) -> tuple[list[WatchedPhraseDict], bool]:
    """Returns the user's watched phrases after the change, along with
    whether any phrase was actually deleted."""
    delete_words_lower = [word.lower() for word in delete_words]
    deleted_count, _ = (
        AlertWord.objects.annotate(word_lower=Lower("word"))
        .filter(
            user_profile=user_profile,
            word_lower__in=delete_words_lower,
        )
        .delete()
    )
    flush_realm_alert_words(user_profile.realm_id)
    return user_watched_phrases(user_profile), deleted_count > 0
