from django.db import models
from django.db.models import CASCADE
from django.db.models.signals import post_delete, post_save

from zerver.lib.cache import (
    cache_delete,
    realm_alert_words_automaton_cache_key,
    realm_alert_words_cache_key,
)
from zerver.models.realms import Realm
from zerver.models.users import UserProfile


class AlertWord(models.Model):
    # Realm isn't necessary, but it's a nice denormalization.  Users
    # never move to another realm, so it's static, and having Realm
    # here optimizes the main query on this table, which is fetching
    # all the alert words in a realm.
    realm = models.ForeignKey(Realm, db_index=True, on_delete=CASCADE)
    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    # Case-insensitive name for the alert word.
    word = models.TextField()

    class Meta:
        unique_together = ("user_profile", "word")


def flush_realm_alert_words(realm_id: int) -> None:
    cache_delete(realm_alert_words_cache_key(realm_id))
    cache_delete(realm_alert_words_automaton_cache_key(realm_id))


def flush_alert_word(*, instance: AlertWord, **kwargs: object) -> None:
    realm_id = instance.realm_id
    flush_realm_alert_words(realm_id)


post_save.connect(flush_alert_word, sender=AlertWord)
post_delete.connect(flush_alert_word, sender=AlertWord)
