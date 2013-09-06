import re

import zerver.models

from zerver.lib.cache import cache_with_key, realm_alert_words_cache_key

import itertools
import logging
import ujson

@cache_with_key(realm_alert_words_cache_key, timeout=3600*24)
def alert_words_in_realm(realm):
    users = zerver.models.UserProfile.objects.filter(realm=realm, is_active=True)
    all_user_words = dict((user, user_alert_words(user)) for user in users)
    users_with_words = dict((u, w) for (u, w) in all_user_words.iteritems() if len(w))
    return users_with_words

def user_alert_words(user_profile):
    return ujson.loads(user_profile.alert_words)

def add_user_alert_words(user_profile, alert_words):
    words = user_alert_words(user_profile)

    new_words = [w for w in alert_words if not w in words]
    words.extend(new_words)

    set_user_alert_words(user_profile, words)

def remove_user_alert_words(user_profile, alert_words):
    words = user_alert_words(user_profile)
    words = [w for w in words if not w in alert_words]

    set_user_alert_words(user_profile, words)

def set_user_alert_words(user_profile, alert_words):
    user_profile.alert_words = ujson.dumps(alert_words)
    user_profile.save(update_fields=['alert_words'])
