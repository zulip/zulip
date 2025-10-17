from collections.abc import Iterable, Sequence

from django.db import transaction

from zerver.lib.alert_words import add_user_alert_words, remove_user_alert_words
from zerver.models import AlertWordRemoval, UserProfile
from zerver.tornado.django_api import send_event_on_commit


def notify_alert_words(user_profile: UserProfile, words: Sequence[str]) -> None:
    event = dict(type="alert_words", alert_words=words)
    send_event_on_commit(user_profile.realm, event, [user_profile.id])


@transaction.atomic(durable=True)
def do_add_alert_words(user_profile: UserProfile, alert_words: Iterable[str]) -> None:
    words = add_user_alert_words(user_profile, alert_words)
    notify_alert_words(user_profile, words)


@transaction.atomic(durable=True)
def do_remove_alert_words(user_profile: UserProfile, alert_words: Iterable[str]) -> None:
    words, removed_words = remove_user_alert_words(user_profile, alert_words)

    # write tombstones for each actually-removed word
    if removed_words:
        AlertWordRemoval.objects.bulk_create(
            AlertWordRemoval(user_profile=user_profile, realm=user_profile.realm, word=w)
            for w in removed_words
        )

    # For the event, we could send only "just removed" with removed_at=now().
    # For now, send the recent list so clients can stay in sync without extra GETs.
    notify_alert_words(user_profile, words)
