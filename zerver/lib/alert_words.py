from zerver.models import UserProfile, Realm, AlertWord
from zerver.lib.cache import cache_with_key, realm_alert_words_cache_key, \
    realm_alert_words_automaton_cache_key
import ahocorasick
from typing import Dict, Iterable, List

@cache_with_key(realm_alert_words_cache_key, timeout=3600*24)
def alert_words_in_realm(realm: Realm) -> Dict[int, List[str]]:
    user_ids_and_words = AlertWord.objects.filter(
        realm=realm, user_profile__is_active=True).values("user_profile_id", "word")
    user_ids_with_words = dict()  # type: Dict[int, List[str]]
    for id_and_word in user_ids_and_words:
        user_ids_with_words.setdefault(id_and_word["user_profile_id"], [])
        user_ids_with_words[id_and_word["user_profile_id"]].append(id_and_word["word"])
    return user_ids_with_words

@cache_with_key(realm_alert_words_automaton_cache_key, timeout=3600*24)
def get_alert_word_automaton(realm: Realm) -> ahocorasick.Automaton:
    user_id_with_words = alert_words_in_realm(realm)
    alert_word_automaton  = ahocorasick.Automaton()
    for (user_id, alert_words) in user_id_with_words.items():
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
    # https://pyahocorasick.readthedocs.io/en/latest/index.html?highlight=Automaton.kind#module-constants
    if alert_word_automaton.kind != ahocorasick.AHOCORASICK:
        return None
    return alert_word_automaton

def user_alert_words(user_profile: UserProfile) -> List[str]:
    return list(AlertWord.objects.filter(user_profile=user_profile).values_list("word", flat=True))

def add_user_alert_words(user_profile: UserProfile, alert_words: Iterable[str]) -> List[str]:
    words = user_alert_words(user_profile)

    new_words = [w for w in alert_words if w not in words]

    # to avoid duplication of words
    new_words = list(set(new_words))

    AlertWord.objects.bulk_create(
        AlertWord(user_profile=user_profile, word=word, realm=user_profile.realm) for word in new_words)

    return words+new_words

def remove_user_alert_words(user_profile: UserProfile, alert_words: Iterable[str]) -> List[str]:
    words = user_alert_words(user_profile)
    delete_words = [w for w in alert_words if w in words]
    AlertWord.objects.filter(user_profile=user_profile, word__in=delete_words).delete()

    return user_alert_words(user_profile)
