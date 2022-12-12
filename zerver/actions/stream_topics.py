import hashlib
from collections import defaultdict
from typing import Any, Collection, Dict, List, Mapping, Optional, Sequence

import orjson
from django.conf import settings
from django.db import transaction
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.lib.streams import (
    can_access_stream_user_ids
)
from zerver.lib.types import APISubscriptionDict
from zerver.models import (
    Realm,
    RealmAuditLog,
    Recipient,
    Stream,
    StreamTopic,
    UserProfile,
    get_stream_topics
)
from zerver.tornado.django_api import send_event


def do_add_pinned_topic_to_stream_topic(
    realm: Realm,
    stream: Stream,
    name: str,
    is_pinned: bool,
    acting_user: Optional[UserProfile] # Currently this feature is not user specific
) -> None:  
    stream_topic = StreamTopic(
        stream_id=stream.id,
        name=name,
        is_pinned=is_pinned,
    )
    stream_topic.save()

    event = dict(
        type="stream_topic",
        stream_id=stream.id,
        name=name,
        is_pinned=is_pinned,
    )
    transaction.on_commit(lambda: send_event(realm, event, [acting_user]))


def do_change_stream_topic_property(
    realm: Realm,
    stream: Stream, 
    stream_topic: StreamTopic, 
    new_is_pinned: bool,
    acting_user: Optional[UserProfile]
) -> None:
    if stream_topic.is_pinned == new_is_pinned:
        return
    with transaction.atomic():
        stream_topic.is_pinned = new_is_pinned
        stream_topic.save(update_fields=["is_pinned"])
        RealmAuditLog.objects.create(
            realm=realm,
            modified_stream=stream,
            modified_stream_topic=stream_topic,
            event_type=RealmAuditLog.STREAMTOPIC_PROPERTY_CHANGED,
            event_time=timezone_now(),
            acting_user=acting_user,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.OLD_VALUE: str(not new_is_pinned),
                    RealmAuditLog.NEW_VALUE: str(new_is_pinned),
                    "property": "is_pinned",
                }
            ).decode(),
        )
    event = dict(
        type="stream_topic",
        op="update",
        property="is_pinned",
        name=stream_topic.name,
        stream_id=stream.id,
        value=new_is_pinned,
    )
    transaction.on_commit(
        lambda: send_event(realm, event, [acting_user])
    )
