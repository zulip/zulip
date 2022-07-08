
import json
from typing import Any, Dict, List, Set, cast
from zerver.models import Client, Draft, Realm, Recipient, ScheduledMessage, UserProfile, get_realm
from zerver.tornado.django_api import send_event
from zerver.lib.message import normalize_body, truncate_topic
import time
from zerver.lib.exceptions import JsonableError, ResourceNotFoundError
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.lib.streams import access_stream_by_id
from zerver.lib.addressee import get_user_profiles_by_ids
from zerver.lib.recipient_users import recipient_for_user_profiles
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

def further_validated_scheduled_message_dict(
    draft_dict: Dict[str, Any], user_profile: UserProfile
) -> Dict[str, Any]:
    """Take a draft_dict that was already validated by draft_dict_validator then
    further sanitize, validate, and transform it. Ultimately return this "further
    validated" draft dict. It will have a slightly different set of keys the values
    for which can be used to directly create a Draft object."""

    content = normalize_body(draft_dict["content"])
    
    print('content: ' + content)

    timestamp = draft_dict.get("deliver_at")
    timestamp = round(timestamp, 6)
    if timestamp < 0:
        # While it's not exactly an invalid timestamp, it's not something
        # we want to allow either.
        raise JsonableError(_("Timestamp must not be negative."))
    deliver_at = timestamp_to_datetime(timestamp)
    
    print('deliver at: ')
    print(deliver_at)
    
    realms = Realm.objects.all()
    print('Realms:')
    print(realms)

    topic = ""
    recipient = None
    to = json.loads(draft_dict["to"])
    sending_client = draft_dict["sending_client"]
    stream = draft_dict["stream"]
    realm_name = draft_dict["realm_name"]
    if draft_dict["type"] == "stream":
        topic = truncate_topic(draft_dict["topic"])
        if "\0" in topic:
            raise JsonableError(_("Topic must not contain null bytes"))
        if len(to) != 1:
            raise JsonableError(_("Must specify exactly 1 stream ID for stream messages"))
        stream, sub = access_stream_by_id(user_profile, to[0])
        recipient = stream.recipient
    elif draft_dict["type"] == "private" and len(to) != 0:
        to_users = get_user_profiles_by_ids(set(to), user_profile.realm)
        try:
            recipient = recipient_for_user_profiles(to_users, False, None, user_profile)
        except ValidationError as e:  # nocoverage
            raise JsonableError(e.messages[0])

    return {
        "recipient": recipient,
        "subject": topic,
        "content": content,
        "scheduled_timestamp": deliver_at,
        "sending_client": sending_client,
        "stream": stream,
        "realm_name": realm_name
    }

def do_create_scheduled_messages(scheduled_message_dicts: List[Dict[str, Any]], user_profile: UserProfile) -> List[ScheduledMessage]:
    """Create drafts in bulk for a given user based on the draft dicts. Since
    currently, the only place this method is being used (apart from tests) is from
    the create_draft view, we assume that the drafts_dicts are syntactically valid
    (i.e. they satisfy the draft_dict_validator)."""
    scheduled_message_objects = []
    for scheduled_message_dict in scheduled_message_dicts:
        valid_schedule_message_dict = further_validated_scheduled_message_dict(scheduled_message_dict, user_profile)
        print('valid_schedule_message_dict')
        print(valid_schedule_message_dict)
        scheduled_message_objects.append(
            ScheduledMessage(
              sender=user_profile,
              recipient=valid_schedule_message_dict["recipient"],
              subject=valid_schedule_message_dict["subject"],
              content=valid_schedule_message_dict["content"],
              sending_client=Client(valid_schedule_message_dict["sending_client"]),
              stream=valid_schedule_message_dict["stream"],
              realm=user_profile.realm,
              scheduled_timestamp=valid_schedule_message_dict["scheduled_timestamp"]
            )
        )

    created_scheduled_message_objects = ScheduledMessage.objects.bulk_create(scheduled_message_objects)

    event = {
        "type": "scheduled_messages",
        "op": "add",
        "scheduled_messages": [scheduled_message.to_dict() for scheduled_message in created_scheduled_message_objects],
    }
    send_event(user_profile.realm, event, [user_profile.id])

    return created_scheduled_message_objects