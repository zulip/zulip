from zerver.models import UserProfile, Realm, AlertWords
from zerver.lib.cache import cache_with_key, realm_alert_words_cache_key, \
    realm_alert_words_automaton_cache_key
import ahocorasick
from typing import Dict, Iterable, List

@cache_with_key(realm_alert_words_cache_key, timeout=3600*24)
def alert_words_in_realm(realm: Realm) -> Dict[int, List[str]]:
    users_query = UserProfile.objects.filter(realm=realm, is_active=True)
    user_ids_with_words = dict()
    for user_profile in users_query:
        alert_words_objects = AlertWords.objects.filter(user_profile=user_profile)
        if len(alert_words_objects):
            alert_words = [alert_word.word for alert_word in alert_words_objects]
            user_ids_with_words[user_profile.id] = alert_words
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
    alert_word_list = []
    for alert in AlertWords.objects.filter(user_profile=user_profile):
        alert_word_list.append(alert.word)
    return alert_word_list

def add_user_alert_words(user_profile: UserProfile, alert_words: Iterable[str]) -> List[str]:
    words = user_alert_words(user_profile)

    new_words = [w for w in alert_words if w not in words]

    for word in new_words:
        AlertWords.objects.create(user_profile= user_profile, word= word)

    return words+new_words

def remove_user_alert_words(user_profile: UserProfile, alert_words: Iterable[str]) -> List[str]:
    words = user_alert_words(user_profile)
    print(alert_words)
    delete_words = [w for w in alert_words if w in words]
    for word in delete_words:
        w = AlertWords.objects.get(user_profile=user_profile, word=word)
        w.delete()

    return user_alert_words(user_profile)

def set_user_alert_words(user_profile: UserProfile, alert_words: List[str]) -> None:
    AlertWords.objects.filter(user_profile=user_profile).delete()
    for word in alert_words:
        AlertWords.objects.create(user_profile= user_profile, word= word)
