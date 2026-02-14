from collections.abc import Iterable
from typing import TypedDict

import ahocorasick
from django.db import transaction

from zerver.lib.cache import (
    cache_with_key,
    realm_alert_words_automaton_cache_key,
    realm_alert_words_cache_key,
)
from zerver.models import AlertWord, Realm, UserProfile
from zerver.models.alert_words import flush_realm_alert_words


class AlertWordData(TypedDict):
    word: str
    automatically_follow_topics: bool


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


def user_alert_words(user_profile: UserProfile) -> list[AlertWordData]:
    return [
        {
            "word": alert_word["word"],
            "automatically_follow_topics": alert_word["follow_topic_containing_alert_word"],
        }
        for alert_word in AlertWord.objects.filter(user_profile=user_profile).values(
            "word", "follow_topic_containing_alert_word"
        )
    ]


def get_alert_words_list_for_event(words: list[AlertWordData]) -> list[str] | list[AlertWordData]:
    if any(word["automatically_follow_topics"] for word in words):
        return words
    return [word["word"] for word in words]


def normalize_alert_words(alert_words: Iterable[str | AlertWordData]) -> list[AlertWordData]:
    normalized_words: list[AlertWordData] = []
    for word in alert_words:
        if isinstance(word, str):
            normalized_words.append({"word": word, "automatically_follow_topics": False})
        else:
            normalized_words.append(word)
    return normalized_words


@transaction.atomic(savepoint=False)
def add_user_alert_words(
    user_profile: UserProfile, new_words: Iterable[str | AlertWordData]
) -> list[AlertWordData]:
    existing_words = {
        word["word"].lower(): word["automatically_follow_topics"]
        for word in user_alert_words(user_profile)
    }

    # Keeping the case, use a dictionary to get the set of
    # case-insensitive distinct, new alert words
    word_dict: dict[str, AlertWordData] = {}
    for word_data in normalize_alert_words(new_words):
        alert_word = word_data["word"]
        follow_topics = word_data["automatically_follow_topics"]
        lower_alert_word = alert_word.lower()

        if lower_alert_word in existing_words:
            if follow_topics != existing_words[lower_alert_word]:
                alert_word_obj = AlertWord.objects.get(
                    user_profile=user_profile, word__iexact=alert_word
                )
                alert_word_obj.follow_topic_containing_alert_word = follow_topics
                alert_word_obj.save(update_fields=["follow_topic_containing_alert_word"])
            continue

        word_dict[lower_alert_word] = word_data

    AlertWord.objects.bulk_create(
        AlertWord(
            user_profile=user_profile,
            word=word_data["word"],
            realm=user_profile.realm,
            follow_topic_containing_alert_word=word_data["automatically_follow_topics"],
        )
        for word_data in word_dict.values()
    )
    # Django bulk_create operations don't flush caches, so we need to do this ourselves.
    flush_realm_alert_words(user_profile.realm_id)

    return user_alert_words(user_profile)


@transaction.atomic(savepoint=False)
def remove_user_alert_words(user_profile: UserProfile, delete_words: Iterable[str]) -> list[AlertWordData]:
    # TODO: Ideally, this would be a bulk query, but Django doesn't have a `__iexact`.
    # We can clean this up if/when PostgreSQL has more native support for case-insensitive fields.
    # If we turn this into a bulk operation, we will need to call flush_realm_alert_words() here.
    for delete_word in delete_words:
        AlertWord.objects.filter(user_profile=user_profile, word__iexact=delete_word).delete()
    return user_alert_words(user_profile)
