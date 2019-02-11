
from django.db.models import Q
from zerver.models import UserProfile, Realm
from zerver.lib.cache import cache_with_key, realm_alert_words_cache_key, \
    realm_alert_words_automaton_cache_key
import ujson
import ahocorasick
from typing import Dict, Iterable, List

@cache_with_key(realm_alert_words_cache_key, timeout=3600*24)
def alert_words_in_realm(realm: Realm) -> Dict[int, List[str]]:
    users_query = UserProfile.objects.filter(realm=realm, is_active=True)
    alert_word_data = users_query.filter(~Q(alert_words=ujson.dumps([]))).values('id', 'alert_words')
    all_user_words = dict((elt['id'], ujson.loads(elt['alert_words'])) for elt in alert_word_data)
    user_ids_with_words = dict((user_id, w) for (user_id, w) in all_user_words.items() if len(w))
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
                alert_word_automaton.add_word(alert_word_lower, (alert_word_lower, set([user_id])))
    alert_word_automaton.make_automaton()
    # If the kind is not AHOCORASICK after calling make_automaton, it means there is no key present
    # and hence we cannot call items on the automaton yet. To avoid it we return None for such cases
    # where there is no alert-words in the realm.
    # https://pyahocorasick.readthedocs.io/en/latest/index.html?highlight=Automaton.kind#module-constants
    if alert_word_automaton.kind != ahocorasick.AHOCORASICK:
        return None
    return alert_word_automaton

def user_alert_words(user_profile: UserProfile) -> List[str]:
    return ujson.loads(user_profile.alert_words)

def add_user_alert_words(user_profile: UserProfile, alert_words: Iterable[str]) -> List[str]:
    words = user_alert_words(user_profile)

    new_words = [w for w in alert_words if w not in words]
    words.extend(new_words)

    set_user_alert_words(user_profile, words)

    return words

def remove_user_alert_words(user_profile: UserProfile, alert_words: Iterable[str]) -> List[str]:
    words = user_alert_words(user_profile)
    words = [w for w in words if w not in alert_words]

    set_user_alert_words(user_profile, words)

    return words

def set_user_alert_words(user_profile: UserProfile, alert_words: List[str]) -> None:
    user_profile.alert_words = ujson.dumps(alert_words)
    user_profile.save(update_fields=['alert_words'])
