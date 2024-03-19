from typing import Dict, Iterable, List, Tuple, Union

import ahocorasick
from django.db import transaction

from zerver.lib.cache import (
    cache_with_key,
    realm_alert_words_automaton_cache_key,
    realm_alert_words_cache_key,
)
from zerver.models import AlertWord, Realm, UserProfile
from zerver.models.alert_words import flush_realm_alert_words


@cache_with_key(lambda realm: realm_alert_words_cache_key(realm.id), timeout=3600 * 24)
def alert_words_in_realm(realm: Realm) -> Dict[int, List[str]]:
    user_ids_and_words = AlertWord.objects.filter(realm=realm, user_profile__is_active=True).values(
        "user_profile_id", "word"
    )
    user_ids_with_words: Dict[int, List[str]] = {}
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


def user_alert_words(user_profile: UserProfile) -> List[Tuple[str, bool]]:
    return list(
        AlertWord.objects.filter(user_profile=user_profile).values_list(
            "word", "follow_topic_containing_alert_word"
        )
    )


def get_alert_words_list_for_event(
    words: List[Tuple[str, bool]],
) -> Union[List[str], List[Tuple[str, bool]]]:
    user_configured_automatic_follow_policy = False
    alert_words: List[str] = []

    for word in words:
        alert_word = word[0]
        automatic_follow_topic_containing_alert_word = word[1]
        if automatic_follow_topic_containing_alert_word:
            user_configured_automatic_follow_policy = True
        alert_words.append(alert_word)

    if user_configured_automatic_follow_policy:
        return words

    return alert_words


def add_follow_topic_field_to_alert_words(
    alert_words: Iterable[Union[str, Tuple[str, bool]]],
) -> Iterable[Tuple[str, bool]]:
    new_alert_words: List[Tuple[str, bool]] = []
    for index, word in enumerate(alert_words):
        if isinstance(word, str):
            assert isinstance(word, str)
            new_alert_words.append((word, False))
        else:
            assert isinstance(word, tuple)
            new_alert_words.append((word[0], word[1]))

    return new_alert_words


@transaction.atomic
def add_user_alert_words(
    user_profile: UserProfile, new_words: Iterable[Union[str, Tuple[str, bool]]]
) -> List[Tuple[str, bool]]:
    existing_words = {word[0].lower(): word[1] for word in user_alert_words(user_profile)}
    existing_words_lower = list(existing_words.keys())

    # Keeping the case, use a dictionary to get the set of
    # case-insensitive distinct, new alert words
    word_dict: Dict[str, Tuple[str, bool]] = {}
    new_alert_words = add_follow_topic_field_to_alert_words(new_words)
    for word in new_alert_words:
        alert_word = word[0]
        follow_topic_containing_alert_word = word[1]
        if alert_word.lower() in existing_words_lower:
            if follow_topic_containing_alert_word != existing_words[alert_word.lower()]:
                alert_word_obj = AlertWord.objects.get(
                    user_profile=user_profile, word__iexact=alert_word
                )
                alert_word_obj.follow_topic_containing_alert_word = (
                    follow_topic_containing_alert_word
                )
                alert_word_obj.save(update_fields=["follow_topic_containing_alert_word"])
            continue
        word_dict[alert_word.lower()] = word

    AlertWord.objects.bulk_create(
        AlertWord(
            user_profile=user_profile,
            word=word[0],
            realm=user_profile.realm,
            follow_topic_containing_alert_word=word[1],
        )
        for word in word_dict.values()
    )
    # Django bulk_create operations don't flush caches, so we need to do this ourselves.
    flush_realm_alert_words(user_profile.realm_id)

    return user_alert_words(user_profile)


@transaction.atomic
def remove_user_alert_words(
    user_profile: UserProfile, delete_words: Iterable[str]
) -> List[Tuple[str, bool]]:
    # TODO: Ideally, this would be a bulk query, but Django doesn't have a `__iexact`.
    # We can clean this up if/when PostgreSQL has more native support for case-insensitive fields.
    # If we turn this into a bulk operation, we will need to call flush_realm_alert_words() here.
    for delete_word in delete_words:
        AlertWord.objects.filter(user_profile=user_profile, word__iexact=delete_word).delete()
    return user_alert_words(user_profile)
