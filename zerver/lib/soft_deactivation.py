from __future__ import absolute_import

from django.db import transaction

from zerver.models import UserProfile, UserMessage, RealmAuditLog

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
