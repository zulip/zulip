from typing import Iterable, Sequence

from zerver.lib.alert_words import add_user_alert_words, remove_user_alert_words
from zerver.models import UserProfile
from zerver.tornado.django_api import send_event


def notify_alert_words(user_profile: UserProfile, words: Sequence[str]) -> None:
    event = dict(type="alert_words", alert_words=words)
    send_event(user_profile.realm, event, [user_profile.id])


def do_add_alert_words(user_profile: UserProfile, alert_words: Iterable[str]) -> None:
    words = add_user_alert_words(user_profile, alert_words)
    notify_alert_words(user_profile, words)


def do_remove_alert_words(user_profile: UserProfile, alert_words: Iterable[str]) -> None:
    words = remove_user_alert_words(user_profile, alert_words)
    notify_alert_words(user_profile, words)
