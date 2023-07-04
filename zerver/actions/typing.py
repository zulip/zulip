from typing import List, Optional

from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.lib.stream_subscription import get_user_ids_for_streams
from zerver.models import Realm, Stream, UserProfile, get_user_by_id_in_realm_including_cross_realm
from zerver.tornado.django_api import send_event


def do_send_typing_notification(
    realm: Realm,
    sender: UserProfile,
    recipient_user_profiles: List[UserProfile],
    operator: str,
    message_id: Optional[int] = None,
) -> None:
    sender_dict = {"user_id": sender.id, "email": sender.email}

    # Include a list of recipients in the event body to help identify where the typing is happening
    recipient_dicts = [
        {"user_id": profile.id, "email": profile.email} for profile in recipient_user_profiles
    ]
    event = dict(
        type="typing",
        message_type="private",
        op=operator,
        sender=sender_dict,
        recipients=recipient_dicts,
        message_id=message_id,
    )

    # Only deliver the notification to active user recipients
    user_ids_to_notify = [user.id for user in recipient_user_profiles if user.is_active]

    send_event(realm, event, user_ids_to_notify)


# Checks the typing notification and sends it
def check_send_typing_notification(
    sender: UserProfile, user_ids: List[int], operator: str, message_id: Optional[int] = None
) -> None:
    realm = sender.realm

    if sender.id not in user_ids:
        user_ids.append(sender.id)

    # If any of the user_ids being sent in are invalid, we will
    # just reject the whole request, since a partial list of user_ids
    # can create confusion related to huddles.  Plus it's a good
    # sign that a client is confused (or possibly even malicious) if
    # we get bad user_ids.
    user_profiles = []
    for user_id in user_ids:
        try:
            # We include cross-bot realms as possible recipients,
            # so that clients can know which huddle conversation
            # is relevant here.
            user_profile = get_user_by_id_in_realm_including_cross_realm(user_id, sender.realm)
        except UserProfile.DoesNotExist:
            raise JsonableError(_("Invalid user ID {}").format(user_id))
        user_profiles.append(user_profile)

    do_send_typing_notification(
        realm=realm,
        sender=sender,
        recipient_user_profiles=user_profiles,
        operator=operator,
        message_id=message_id,
    )


def do_send_stream_typing_notification(
    sender: UserProfile,
    operator: str,
    stream: Stream,
    topic: str,
    message_id: Optional[int] = None,
) -> None:
    sender_dict = {"user_id": sender.id, "email": sender.email}

    event = dict(
        type="typing",
        message_type="stream",
        op=operator,
        sender=sender_dict,
        stream_id=stream.id,
        topic=topic,
        message_id=message_id,
    )

    user_ids_to_notify = get_user_ids_for_streams({stream.id})[stream.id]

    send_event(sender.realm, event, user_ids_to_notify)
