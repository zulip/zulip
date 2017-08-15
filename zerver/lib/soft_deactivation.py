from __future__ import absolute_import

from django.db import transaction
from django.db.models import Max

from zerver.models import (
    UserProfile, UserMessage, RealmAuditLog, Realm, UserActivity
)
from zerver.lib.message import maybe_catch_up_soft_deactivated_user

from django.utils.timezone import now as timezone_now

from typing import List

def do_soft_deactivate_user(user):
    # type: (UserProfile) -> None
    user.last_active_message_id = UserMessage.objects.filter(
        user_profile=user).order_by(
        '-message__id')[0].message_id
    user.long_term_idle = True
    user.save(update_fields=[
        'long_term_idle',
        'last_active_message_id'])

def do_soft_deactivate_users(users):
    # type: (List[UserProfile]) -> None
    with transaction.atomic():
        realm_logs = []
        for user in users:
            do_soft_deactivate_user(user)
            event_time = timezone_now()
            log = RealmAuditLog(
                realm=user.realm,
                modified_user=user,
                event_type='user_soft_deactivated',
                event_time=event_time
            )
            realm_logs.append(log)
        RealmAuditLog.objects.bulk_create(realm_logs)

def get_users_for_soft_deactivation(realm, inactive_for_days):
    # type: (Realm, int) -> List[UserProfile]
    users_activity = list(UserActivity.objects.filter(
        user_profile__realm=realm,
        user_profile__is_bot=False,
        user_profile__long_term_idle=False).values(
        'user_profile_id').annotate(last_visit=Max('last_visit')))
    user_ids_to_deactivate = []
    today = timezone_now()
    for user in users_activity:
        if (today - user['last_visit']).days > inactive_for_days:
            user_ids_to_deactivate.append(user['user_profile_id'])
    users_to_deactivate = list(UserProfile.objects.filter(
        id__in=user_ids_to_deactivate))
    return users_to_deactivate

def do_soft_activate_users(users):
    # type: (List[UserProfile]) -> None
    for user in users:
        maybe_catch_up_soft_deactivated_user(user)
