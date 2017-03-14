from __future__ import absolute_import
from __future__ import print_function

from datetime import timedelta
from django.utils import timezone
from zerver.models import Realm, Message

from typing import Any, Dict, Optional, Generator


def get_realm_expired_messages(realm):
    # type: (Any) -> Optional[Dict[str, Any]]
    expired_date = timezone.now() - timedelta(days=realm.message_retention_days)
    expired_messages = Message.objects.order_by('id').filter(sender__realm=realm,
                                                             pub_date__lt=expired_date)
    if not expired_messages.exists():
        return None
    return {'realm_id': realm.id, 'expired_messages': expired_messages}


def get_expired_messages():
    # type: () -> Generator[Any, None, None]
    # Get all expired messages by Realm.
    realms = Realm.objects.order_by('string_id').filter(
        deactivated=False, message_retention_days__isnull=False)
    for realm in realms:
        realm_expired_messages = get_realm_expired_messages(realm)
        if realm_expired_messages:
            yield realm_expired_messages
