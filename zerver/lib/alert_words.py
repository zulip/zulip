from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

import ahocorasick
from django.db import transaction
from django.utils.timezone import now

from zerver.lib.cache import (
    cache_with_key,
    realm_alert_words_automaton_cache_key,
    realm_alert_words_cache_key,
)
from zerver.models import AlertWord, AlertWordRemoval, Realm, UserProfile
from zerver.models.alert_words import flush_realm_alert_words

DEFAULT_REMOVAL_RETENTION_DAYS = 90


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
                (key, user_ids_for_alert_word) = alert_word_automaton.get(alert_word_lower)
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


@transaction.atomic(savepoint=False)
def add_user_alert_words(user_profile: UserProfile, new_words: Iterable[str]) -> list[str]:
    existing_words_lower = {word.lower() for word in user_alert_words(user_profile)}

    # Keeping the case, use a dictionary to get the set of
    # case-insensitive distinct, new alert words
    word_dict: dict[str, str] = {}
    for word in new_words:
        if word.lower() in existing_words_lower:
            continue
        word_dict[word.lower()] = word

    AlertWord.objects.bulk_create(
        AlertWord(user_profile=user_profile, word=word, realm=user_profile.realm)
        for word in word_dict.values()
    )
    # Django bulk_create operations don't flush caches, so we need to do this ourselves.
    flush_realm_alert_words(user_profile.realm_id)

    return user_alert_words(user_profile)


@transaction.atomic(savepoint=False)
def remove_user_alert_words(
    user_profile: UserProfile, delete_words: Iterable[str]
) -> tuple[list[str], list[str]]:
    # TODO: Ideally, this would be a bulk query, but Django doesn't have a `__iexact`.
    # We can clean this up if/when PostgreSQL has more native support for case-insensitive fields.
    # If we turn this into a bulk operation, we will need to call flush_realm_alert_words() here.

    removed_words: list[str] = []
    for delete_word in delete_words:
        # Capture originals (case-preserving) before delete
        originals = list(
            AlertWord.objects.filter(
                user_profile=user_profile, word__iexact=delete_word
            ).values_list("word", flat=True)
        )
        if originals:
            removed_words.extend(originals)
            AlertWord.objects.filter(user_profile=user_profile, word__iexact=delete_word).delete()
    return user_alert_words(user_profile), removed_words


def recently_removed_alert_words(
    user_profile: UserProfile,
    since: datetime | None = None,
    retention_days: int = DEFAULT_REMOVAL_RETENTION_DAYS,
) -> list[dict[str, Any]]:
    # Return recent removals for this user.
    # We limit to a recent window to keep payloads small.

    qs = AlertWordRemoval.objects.filter(user_profile=user_profile)
    if since is not None:
        qs = qs.filter(removed_at__gte=since)
    else:
        qs = qs.filter(removed_at__gte=now() - timedelta(days=retention_days))

    return [
        {"word": row.word, "removed_at": row.removed_at.isoformat()}
        for row in qs.order_by("-removed_at")
    ]
