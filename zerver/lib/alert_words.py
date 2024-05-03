from typing import Dict, Iterable, List

import ahocorasick
from django.db import transaction
from pydantic import BaseModel, ConfigDict, StringConstraints
from typing_extensions import Annotated

from zerver.lib.cache import (
    cache_with_key,
    realm_watched_phrases_automaton_cache_key,
    realm_watched_phrases_cache_key,
)
from zerver.models import AlertWord, Realm, UserProfile
from zerver.models.alert_words import flush_realm_watched_phrases


class WatchedPhraseData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    watched_phrase: Annotated[str, StringConstraints(max_length=100)]


@cache_with_key(lambda realm: realm_watched_phrases_cache_key(realm.id), timeout=3600 * 24)
def watched_phrases_in_realm(realm: Realm) -> Dict[int, List[str]]:
    user_ids_and_phrases = AlertWord.objects.filter(
        realm=realm, user_profile__is_active=True
    ).values("user_profile_id", "watched_phrase")
    user_ids_with_phrases: Dict[int, List[str]] = {}
    for id_and_phrase in user_ids_and_phrases:
        user_ids_with_phrases.setdefault(id_and_phrase["user_profile_id"], [])
        user_ids_with_phrases[id_and_phrase["user_profile_id"]].append(
            id_and_phrase["watched_phrase"]
        )
    return user_ids_with_phrases


@cache_with_key(
    lambda realm: realm_watched_phrases_automaton_cache_key(realm.id), timeout=3600 * 24
)
def get_watched_phrases_automaton(realm: Realm) -> ahocorasick.Automaton:
    user_id_with_phrases = watched_phrases_in_realm(realm)
    watched_phrase_automaton = ahocorasick.Automaton()
    for user_id, watched_phrases in user_id_with_phrases.items():
        for watched_phrase in watched_phrases:
            watched_phrase_lower = watched_phrase.lower()
            if watched_phrase_automaton.exists(watched_phrase_lower):
                (key, user_ids_for_watched_phrase) = watched_phrase_automaton.get(
                    watched_phrase_lower
                )
                user_ids_for_watched_phrase.add(user_id)
            else:
                watched_phrase_automaton.add_word(
                    watched_phrase_lower, (watched_phrase_lower, {user_id})
                )
    watched_phrase_automaton.make_automaton()
    # If the kind is not AHOCORASICK after calling make_automaton, it means there is no key present
    # and hence we cannot call items on the automaton yet. To avoid it we return None for such cases
    # where there is no alert-words in the realm.
    # https://pyahocorasick.readthedocs.io/en/latest/#make-automaton
    if watched_phrase_automaton.kind != ahocorasick.AHOCORASICK:
        return None
    return watched_phrase_automaton


def user_alert_words(user_profile: UserProfile) -> List[str]:
    return list(
        AlertWord.objects.filter(user_profile=user_profile).values_list("watched_phrase", flat=True)
    )


def user_watched_phrases(user_profile: UserProfile) -> List[WatchedPhraseData]:
    watched_phrase_data = [
        WatchedPhraseData(watched_phrase=watched_phrase)
        for watched_phrase in AlertWord.objects.filter(user_profile=user_profile).values_list(
            "watched_phrase", flat=True
        )
    ]
    return watched_phrase_data


@transaction.atomic
def add_user_watched_phrases(
    user_profile: UserProfile, new_phrases: Iterable[WatchedPhraseData]
) -> List[WatchedPhraseData]:
    existing_phrases_lower = {
        phrase.watched_phrase.lower() for phrase in user_watched_phrases(user_profile)
    }

    # Keeping the case, use a dictionary to get the set of
    # case-insensitive distinct, new alert words
    watched_phrases_dict: Dict[str, WatchedPhraseData] = {}
    for phrase in new_phrases:
        if phrase.watched_phrase.lower() in existing_phrases_lower:
            continue
        watched_phrases_dict[phrase.watched_phrase.lower()] = phrase

    AlertWord.objects.bulk_create(
        AlertWord(
            user_profile=user_profile,
            watched_phrase=phrase.watched_phrase,
            realm=user_profile.realm,
        )
        for phrase in watched_phrases_dict.values()
    )
    # Django bulk_create operations don't flush caches, so we need to do this ourselves.
    flush_realm_watched_phrases(user_profile.realm_id)

    return user_watched_phrases(user_profile)


@transaction.atomic
def remove_user_watched_phrases(
    user_profile: UserProfile, delete_phrases: Iterable[str]
) -> List[WatchedPhraseData]:
    # TODO: Ideally, this would be a bulk query, but Django doesn't have a `__iexact`.
    # We can clean this up if/when PostgreSQL has more native support for case-insensitive fields.
    # If we turn this into a bulk operation, we will need to call flush_realm_watched_phrases() here.
    for delete_phrase in delete_phrases:
        AlertWord.objects.filter(
            user_profile=user_profile, watched_phrase__iexact=delete_phrase
        ).delete()
    return user_watched_phrases(user_profile)
