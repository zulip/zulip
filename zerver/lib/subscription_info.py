from typing import Dict

from zerver.lib.email_mirror_helpers import encode_email_address_helper
from zerver.lib.stream_color import STREAM_ASSIGNMENT_COLORS
from zerver.lib.stream_traffic import get_average_weekly_stream_traffic
from zerver.lib.streams import get_web_public_streams_queryset
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.types import (
    NeverSubscribedStreamDict,
    RawStreamDict,
    RawSubscriptionDict,
    SubscriptionInfo,
    SubscriptionStreamDict,
)
from zerver.models import Realm, Stream, Subscription, UserProfile


def get_web_public_subs(realm: Realm) -> SubscriptionInfo:
    color_idx = 0

    def get_next_color() -> str:
        nonlocal color_idx
        color = STREAM_ASSIGNMENT_COLORS[color_idx]
        color_idx = (color_idx + 1) % len(STREAM_ASSIGNMENT_COLORS)
        return color

    subscribed = []
    for stream in get_web_public_streams_queryset(realm):
        # Add Stream fields.
        date_created = datetime_to_timestamp(stream.date_created)
        description = stream.description
        first_message_id = stream.first_message_id
        history_public_to_subscribers = stream.history_public_to_subscribers
        invite_only = stream.invite_only
        is_announcement_only = stream.stream_post_policy == Stream.STREAM_POST_POLICY_ADMINS
        is_web_public = stream.is_web_public
        message_retention_days = stream.message_retention_days
        name = stream.name
        rendered_description = stream.rendered_description
        stream_id = stream.id
        stream_post_policy = stream.stream_post_policy

        # Add versions of the Subscription fields based on a simulated
        # new user subscription set.
        audible_notifications = True
        color = get_next_color()
        desktop_notifications = True
        email_address = ""
        email_notifications = True
        in_home_view = True
        is_muted = False
        pin_to_top = False
        push_notifications = True
        role = Subscription.ROLE_MEMBER
        stream_weekly_traffic = get_average_weekly_stream_traffic(
            stream.id, stream.date_created, {}
        )
        wildcard_mentions_notify = True

        sub = SubscriptionStreamDict(
            audible_notifications=audible_notifications,
            color=color,
            date_created=date_created,
            description=description,
            desktop_notifications=desktop_notifications,
            email_address=email_address,
            email_notifications=email_notifications,
            first_message_id=first_message_id,
            history_public_to_subscribers=history_public_to_subscribers,
            in_home_view=in_home_view,
            invite_only=invite_only,
            is_announcement_only=is_announcement_only,
            is_muted=is_muted,
            is_web_public=is_web_public,
            message_retention_days=message_retention_days,
            name=name,
            pin_to_top=pin_to_top,
            push_notifications=push_notifications,
            rendered_description=rendered_description,
            role=role,
            stream_id=stream_id,
            stream_post_policy=stream_post_policy,
            stream_weekly_traffic=stream_weekly_traffic,
            wildcard_mentions_notify=wildcard_mentions_notify,
        )
        subscribed.append(sub)

    return SubscriptionInfo(
        subscriptions=subscribed,
        unsubscribed=[],
        never_subscribed=[],
    )


def build_stream_dict_for_sub(
    user: UserProfile,
    sub_dict: RawSubscriptionDict,
    raw_stream_dict: RawStreamDict,
    recent_traffic: Dict[int, int],
) -> SubscriptionStreamDict:
    # Handle Stream.API_FIELDS
    date_created = datetime_to_timestamp(raw_stream_dict["date_created"])
    description = raw_stream_dict["description"]
    first_message_id = raw_stream_dict["first_message_id"]
    history_public_to_subscribers = raw_stream_dict["history_public_to_subscribers"]
    invite_only = raw_stream_dict["invite_only"]
    is_web_public = raw_stream_dict["is_web_public"]
    message_retention_days = raw_stream_dict["message_retention_days"]
    name = raw_stream_dict["name"]
    rendered_description = raw_stream_dict["rendered_description"]
    stream_id = raw_stream_dict["id"]
    stream_post_policy = raw_stream_dict["stream_post_policy"]

    # Handle Subscription.API_FIELDS.
    color = sub_dict["color"]
    is_muted = sub_dict["is_muted"]
    pin_to_top = sub_dict["pin_to_top"]
    audible_notifications = sub_dict["audible_notifications"]
    desktop_notifications = sub_dict["desktop_notifications"]
    email_notifications = sub_dict["email_notifications"]
    push_notifications = sub_dict["push_notifications"]
    wildcard_mentions_notify = sub_dict["wildcard_mentions_notify"]
    role = sub_dict["role"]

    # Backwards-compatibility for clients that haven't been
    # updated for the in_home_view => is_muted API migration.
    in_home_view = not is_muted

    # Backwards-compatibility for clients that haven't been
    # updated for the is_announcement_only -> stream_post_policy
    # migration.
    is_announcement_only = raw_stream_dict["stream_post_policy"] == Stream.STREAM_POST_POLICY_ADMINS

    # Add a few computed fields not directly from the data models.
    stream_weekly_traffic = get_average_weekly_stream_traffic(
        raw_stream_dict["id"], raw_stream_dict["date_created"], recent_traffic
    )

    email_address = encode_email_address_helper(
        raw_stream_dict["name"], raw_stream_dict["email_token"], show_sender=True
    )

    # Our caller may add a subscribers field.
    return SubscriptionStreamDict(
        audible_notifications=audible_notifications,
        color=color,
        date_created=date_created,
        description=description,
        desktop_notifications=desktop_notifications,
        email_address=email_address,
        email_notifications=email_notifications,
        first_message_id=first_message_id,
        history_public_to_subscribers=history_public_to_subscribers,
        in_home_view=in_home_view,
        invite_only=invite_only,
        is_announcement_only=is_announcement_only,
        is_muted=is_muted,
        is_web_public=is_web_public,
        message_retention_days=message_retention_days,
        name=name,
        pin_to_top=pin_to_top,
        push_notifications=push_notifications,
        rendered_description=rendered_description,
        role=role,
        stream_id=stream_id,
        stream_post_policy=stream_post_policy,
        stream_weekly_traffic=stream_weekly_traffic,
        wildcard_mentions_notify=wildcard_mentions_notify,
    )


def build_stream_dict_for_never_sub(
    raw_stream_dict: RawStreamDict,
    recent_traffic: Dict[int, int],
) -> NeverSubscribedStreamDict:
    date_created = datetime_to_timestamp(raw_stream_dict["date_created"])
    description = raw_stream_dict["description"]
    first_message_id = raw_stream_dict["first_message_id"]
    history_public_to_subscribers = raw_stream_dict["history_public_to_subscribers"]
    invite_only = raw_stream_dict["invite_only"]
    is_web_public = raw_stream_dict["is_web_public"]
    message_retention_days = raw_stream_dict["message_retention_days"]
    name = raw_stream_dict["name"]
    rendered_description = raw_stream_dict["rendered_description"]
    stream_id = raw_stream_dict["id"]
    stream_post_policy = raw_stream_dict["stream_post_policy"]
    stream_weekly_traffic = get_average_weekly_stream_traffic(
        raw_stream_dict["id"], raw_stream_dict["date_created"], recent_traffic
    )

    # Backwards-compatibility addition of removed field.
    is_announcement_only = raw_stream_dict["stream_post_policy"] == Stream.STREAM_POST_POLICY_ADMINS

    # Our caller may add a subscribers field.
    return NeverSubscribedStreamDict(
        date_created=date_created,
        description=description,
        first_message_id=first_message_id,
        history_public_to_subscribers=history_public_to_subscribers,
        invite_only=invite_only,
        is_announcement_only=is_announcement_only,
        is_web_public=is_web_public,
        message_retention_days=message_retention_days,
        name=name,
        rendered_description=rendered_description,
        stream_id=stream_id,
        stream_post_policy=stream_post_policy,
        stream_weekly_traffic=stream_weekly_traffic,
    )
