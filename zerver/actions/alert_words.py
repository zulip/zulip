from typing import Iterable, List, Tuple, Union

from zerver.lib.alert_words import (
    add_user_alert_words,
    get_alert_words_list_for_event,
    remove_user_alert_words,
)
from zerver.models import UserProfile
from zerver.tornado.django_api import send_event


def notify_alert_words(user_profile: UserProfile, words: List[Tuple[str, bool]]) -> None:
    event = dict(type="alert_words", alert_words=get_alert_words_list_for_event(words))
    send_event(user_profile.realm, event, [user_profile.id])


def do_add_alert_words(
    user_profile: UserProfile, alert_words: Iterable[Union[str, Tuple[str, bool]]]
) -> None:
    words = add_user_alert_words(user_profile, alert_words)
    notify_alert_words(user_profile, words)


def do_remove_alert_words(user_profile: UserProfile, alert_words: Iterable[str]) -> None:
    words = remove_user_alert_words(user_profile, alert_words)
    notify_alert_words(user_profile, words)
