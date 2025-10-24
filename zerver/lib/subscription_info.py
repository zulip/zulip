import itertools
from collections.abc import Callable, Collection, Iterable, Mapping
from operator import itemgetter
from typing import Any, Literal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import QuerySet
from django.utils.translation import gettext as _
from psycopg2.sql import SQL

from zerver.lib.exceptions import JsonableError
from zerver.lib.stream_color import STREAM_ASSIGNMENT_COLORS
from zerver.lib.stream_subscription import (
    SubscriberPeerInfo,
    get_active_subscriptions_for_stream_id,
    get_stream_subscriptions_for_user,
    get_user_ids_for_streams,
)
from zerver.lib.stream_traffic import get_average_weekly_stream_traffic, get_streams_traffic
from zerver.lib.streams import (
    get_stream_post_policy_value_based_on_group_setting,
    get_users_dict_with_metadata_access_to_streams_via_permission_groups,
    get_web_public_streams_queryset,
    has_metadata_access_to_channel_via_groups,
    subscribed_to_stream,
)
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.types import (
    APIStreamDict,
    NeverSubscribedStreamDict,
    RawStreamDict,
    RawSubscriptionDict,
    SubscriptionInfo,
    SubscriptionStreamDict,
    UserGroupMembersData,
)
from zerver.lib.user_groups import (
    UserGroupMembershipDetails,
    get_group_setting_value_for_register_api,
    get_members_and_subgroups_of_groups,
    get_recursive_membership_groups,
)
from zerver.models import Realm, Stream, Subscription, UserGroup, UserProfile
from zerver.models.streams import StreamTopicsPolicyEnum, get_all_streams


def get_web_public_subs(
    realm: Realm, anonymous_group_membership: dict[int, UserGroupMembersData]
) -> SubscriptionInfo:
    color_idx = 0

    def get_next_color() -> str:
        nonlocal color_idx
        color = STREAM_ASSIGNMENT_COLORS[color_idx]
        color_idx = (color_idx + 1) % len(STREAM_ASSIGNMENT_COLORS)
        return color

    subscribed = []
    streams = get_web_public_streams_queryset(realm).select_related(
        "can_send_message_group", "can_send_message_group__named_user_group"
    )

    for stream in streams:
        # Add Stream fields.
        is_archived = stream.deactivated
        can_add_subscribers_group = get_group_setting_value_for_register_api(
            stream.can_add_subscribers_group_id, anonymous_group_membership
        )
        can_administer_channel_group = get_group_setting_value_for_register_api(
            stream.can_administer_channel_group_id, anonymous_group_membership
        )
        can_create_topic_group = get_group_setting_value_for_register_api(
            stream.can_create_topic_group_id, anonymous_group_membership
        )
        can_delete_any_message_group = get_group_setting_value_for_register_api(
            stream.can_delete_any_message_group_id, anonymous_group_membership
        )
        can_delete_own_message_group = get_group_setting_value_for_register_api(
            stream.can_delete_own_message_group_id, anonymous_group_membership
        )
        can_move_messages_out_of_channel_group = get_group_setting_value_for_register_api(
            stream.can_move_messages_out_of_channel_group_id, anonymous_group_membership
        )
        can_move_messages_within_channel_group = get_group_setting_value_for_register_api(
            stream.can_move_messages_within_channel_group_id, anonymous_group_membership
        )
        can_send_message_group = get_group_setting_value_for_register_api(
            stream.can_send_message_group_id, anonymous_group_membership
        )
        can_remove_subscribers_group = get_group_setting_value_for_register_api(
            stream.can_remove_subscribers_group_id, anonymous_group_membership
        )
        can_resolve_topics_group = get_group_setting_value_for_register_api(
            stream.can_resolve_topics_group_id, anonymous_group_membership
        )
        can_subscribe_group = get_group_setting_value_for_register_api(
            stream.can_subscribe_group_id, anonymous_group_membership
        )
        creator_id = stream.creator_id
        date_created = datetime_to_timestamp(stream.date_created)
        description = stream.description
        first_message_id = stream.first_message_id
        folder_id = stream.folder_id
        is_recently_active = stream.is_recently_active
        history_public_to_subscribers = stream.history_public_to_subscribers
        invite_only = stream.invite_only
        is_web_public = stream.is_web_public
        message_retention_days = stream.message_retention_days
        name = stream.name
        rendered_description = stream.rendered_description
        stream_id = stream.id
        stream_post_policy = get_stream_post_policy_value_based_on_group_setting(
            stream.can_send_message_group
        )
        topics_policy = stream.topics_policy
        is_announcement_only = stream_post_policy == Stream.STREAM_POST_POLICY_ADMINS

        # Add versions of the Subscription fields based on a simulated
        # new user subscription set.
        audible_notifications = True
        color = get_next_color()
        desktop_notifications = True
        email_notifications = True
        in_home_view = True
        is_muted = False
        pin_to_top = False
        push_notifications = True
        stream_weekly_traffic = get_average_weekly_stream_traffic(
            stream.id, stream.date_created, {}
        )
        wildcard_mentions_notify = True

        sub = SubscriptionStreamDict(
            is_archived=is_archived,
            audible_notifications=audible_notifications,
            can_add_subscribers_group=can_add_subscribers_group,
            can_administer_channel_group=can_administer_channel_group,
            can_create_topic_group=can_create_topic_group,
            can_delete_any_message_group=can_delete_any_message_group,
            can_delete_own_message_group=can_delete_own_message_group,
            can_move_messages_out_of_channel_group=can_move_messages_out_of_channel_group,
            can_move_messages_within_channel_group=can_move_messages_within_channel_group,
            can_send_message_group=can_send_message_group,
            can_remove_subscribers_group=can_remove_subscribers_group,
            can_resolve_topics_group=can_resolve_topics_group,
            can_subscribe_group=can_subscribe_group,
            color=color,
            creator_id=creator_id,
            date_created=date_created,
            description=description,
            desktop_notifications=desktop_notifications,
            email_notifications=email_notifications,
            first_message_id=first_message_id,
            folder_id=folder_id,
            is_recently_active=is_recently_active,
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
            stream_id=stream_id,
            stream_post_policy=stream_post_policy,
            stream_weekly_traffic=stream_weekly_traffic,
            subscriber_count=stream.subscriber_count,
            topics_policy=StreamTopicsPolicyEnum(topics_policy).name,
            wildcard_mentions_notify=wildcard_mentions_notify,
        )
        subscribed.append(sub)

    return SubscriptionInfo(
        subscriptions=subscribed,
        unsubscribed=[],
        never_subscribed=[],
    )


def build_unsubscribed_sub_from_stream_dict(
    user: UserProfile, sub_dict: RawSubscriptionDict, stream_dict: APIStreamDict
) -> SubscriptionStreamDict:
    subscription_stream_dict = build_stream_dict_for_sub(user, sub_dict, stream_dict)

    return subscription_stream_dict


def build_stream_api_dict(
    raw_stream_dict: RawStreamDict,
    recent_traffic: dict[int, int] | None,
    anonymous_group_membership: dict[int, UserGroupMembersData],
) -> APIStreamDict:
    # Add a few computed fields not directly from the data models.
    if recent_traffic is not None:
        stream_weekly_traffic = get_average_weekly_stream_traffic(
            raw_stream_dict["id"], raw_stream_dict["date_created"], recent_traffic
        )
    else:  # nocoverage
        stream_weekly_traffic = None

    # Backwards-compatibility for clients that haven't been
    # updated for the is_announcement_only -> stream_post_policy
    # migration.
    is_announcement_only = raw_stream_dict["stream_post_policy"] == Stream.STREAM_POST_POLICY_ADMINS

    can_add_subscribers_group = get_group_setting_value_for_register_api(
        raw_stream_dict["can_add_subscribers_group_id"], anonymous_group_membership
    )
    can_administer_channel_group = get_group_setting_value_for_register_api(
        raw_stream_dict["can_administer_channel_group_id"], anonymous_group_membership
    )
    can_create_topic_group = get_group_setting_value_for_register_api(
        raw_stream_dict["can_create_topic_group_id"], anonymous_group_membership
    )
    can_delete_any_message_group = get_group_setting_value_for_register_api(
        raw_stream_dict["can_delete_any_message_group_id"], anonymous_group_membership
    )
    can_delete_own_message_group = get_group_setting_value_for_register_api(
        raw_stream_dict["can_delete_own_message_group_id"], anonymous_group_membership
    )
    can_move_messages_out_of_channel_group = get_group_setting_value_for_register_api(
        raw_stream_dict["can_move_messages_out_of_channel_group_id"], anonymous_group_membership
    )
    can_move_messages_within_channel_group = get_group_setting_value_for_register_api(
        raw_stream_dict["can_move_messages_within_channel_group_id"], anonymous_group_membership
    )
    can_send_message_group = get_group_setting_value_for_register_api(
        raw_stream_dict["can_send_message_group_id"], anonymous_group_membership
    )
    can_remove_subscribers_group = get_group_setting_value_for_register_api(
        raw_stream_dict["can_remove_subscribers_group_id"], anonymous_group_membership
    )
    can_resolve_topics_group = get_group_setting_value_for_register_api(
        raw_stream_dict["can_resolve_topics_group_id"], anonymous_group_membership
    )
    can_subscribe_group = get_group_setting_value_for_register_api(
        raw_stream_dict["can_subscribe_group_id"], anonymous_group_membership
    )

    return APIStreamDict(
        is_archived=raw_stream_dict["deactivated"],
        can_add_subscribers_group=can_add_subscribers_group,
        can_administer_channel_group=can_administer_channel_group,
        can_create_topic_group=can_create_topic_group,
        can_delete_any_message_group=can_delete_any_message_group,
        can_delete_own_message_group=can_delete_own_message_group,
        can_move_messages_out_of_channel_group=can_move_messages_out_of_channel_group,
        can_move_messages_within_channel_group=can_move_messages_within_channel_group,
        can_send_message_group=can_send_message_group,
        can_remove_subscribers_group=can_remove_subscribers_group,
        can_subscribe_group=can_subscribe_group,
        can_resolve_topics_group=can_resolve_topics_group,
        creator_id=raw_stream_dict["creator_id"],
        date_created=datetime_to_timestamp(raw_stream_dict["date_created"]),
        description=raw_stream_dict["description"],
        first_message_id=raw_stream_dict["first_message_id"],
        folder_id=raw_stream_dict["folder_id"],
        history_public_to_subscribers=raw_stream_dict["history_public_to_subscribers"],
        invite_only=raw_stream_dict["invite_only"],
        is_web_public=raw_stream_dict["is_web_public"],
        message_retention_days=raw_stream_dict["message_retention_days"],
        name=raw_stream_dict["name"],
        rendered_description=raw_stream_dict["rendered_description"],
        stream_id=raw_stream_dict["id"],
        stream_post_policy=raw_stream_dict["stream_post_policy"],
        stream_weekly_traffic=stream_weekly_traffic,
        subscriber_count=raw_stream_dict["subscriber_count"],
        topics_policy=raw_stream_dict["topics_policy"],
        is_announcement_only=is_announcement_only,
        is_recently_active=raw_stream_dict["is_recently_active"],
    )


def build_stream_dict_for_sub(
    user: UserProfile,
    sub_dict: RawSubscriptionDict,
    stream_dict: APIStreamDict,
) -> SubscriptionStreamDict:
    # Handle Stream.API_FIELDS
    is_archived = stream_dict["is_archived"]
    can_add_subscribers_group = stream_dict["can_add_subscribers_group"]
    can_administer_channel_group = stream_dict["can_administer_channel_group"]
    can_create_topic_group = stream_dict["can_create_topic_group"]
    can_delete_any_message_group = stream_dict["can_delete_any_message_group"]
    can_delete_own_message_group = stream_dict["can_delete_own_message_group"]
    can_move_messages_out_of_channel_group = stream_dict["can_move_messages_out_of_channel_group"]
    can_move_messages_within_channel_group = stream_dict["can_move_messages_within_channel_group"]
    can_send_message_group = stream_dict["can_send_message_group"]
    can_remove_subscribers_group = stream_dict["can_remove_subscribers_group"]
    can_resolve_topics_group = stream_dict["can_resolve_topics_group"]
    can_subscribe_group = stream_dict["can_subscribe_group"]
    creator_id = stream_dict["creator_id"]
    date_created = stream_dict["date_created"]
    description = stream_dict["description"]
    first_message_id = stream_dict["first_message_id"]
    folder_id = stream_dict["folder_id"]
    history_public_to_subscribers = stream_dict["history_public_to_subscribers"]
    invite_only = stream_dict["invite_only"]
    is_web_public = stream_dict["is_web_public"]
    message_retention_days = stream_dict["message_retention_days"]
    name = stream_dict["name"]
    rendered_description = stream_dict["rendered_description"]
    stream_id = stream_dict["stream_id"]
    stream_post_policy = stream_dict["stream_post_policy"]
    stream_weekly_traffic = stream_dict["stream_weekly_traffic"]
    subscriber_count = stream_dict["subscriber_count"]
    topics_policy = stream_dict["topics_policy"]
    is_announcement_only = stream_dict["is_announcement_only"]
    is_recently_active = stream_dict["is_recently_active"]

    # Handle Subscription.API_FIELDS.
    color = sub_dict["color"]
    is_muted = sub_dict["is_muted"]
    pin_to_top = sub_dict["pin_to_top"]
    audible_notifications = sub_dict["audible_notifications"]
    desktop_notifications = sub_dict["desktop_notifications"]
    email_notifications = sub_dict["email_notifications"]
    push_notifications = sub_dict["push_notifications"]
    wildcard_mentions_notify = sub_dict["wildcard_mentions_notify"]

    # Backwards-compatibility for clients that haven't been
    # updated for the in_home_view => is_muted API migration.
    in_home_view = not is_muted

    # Our caller may add a subscribers field.
    return SubscriptionStreamDict(
        is_archived=is_archived,
        audible_notifications=audible_notifications,
        can_add_subscribers_group=can_add_subscribers_group,
        can_administer_channel_group=can_administer_channel_group,
        can_create_topic_group=can_create_topic_group,
        can_delete_any_message_group=can_delete_any_message_group,
        can_delete_own_message_group=can_delete_own_message_group,
        can_move_messages_out_of_channel_group=can_move_messages_out_of_channel_group,
        can_move_messages_within_channel_group=can_move_messages_within_channel_group,
        can_send_message_group=can_send_message_group,
        can_remove_subscribers_group=can_remove_subscribers_group,
        can_resolve_topics_group=can_resolve_topics_group,
        can_subscribe_group=can_subscribe_group,
        color=color,
        creator_id=creator_id,
        date_created=date_created,
        description=description,
        desktop_notifications=desktop_notifications,
        email_notifications=email_notifications,
        first_message_id=first_message_id,
        folder_id=folder_id,
        is_recently_active=is_recently_active,
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
        stream_id=stream_id,
        stream_post_policy=stream_post_policy,
        stream_weekly_traffic=stream_weekly_traffic,
        subscriber_count=subscriber_count,
        topics_policy=topics_policy,
        wildcard_mentions_notify=wildcard_mentions_notify,
    )


def build_stream_dict_for_never_sub(
    raw_stream_dict: RawStreamDict,
    recent_traffic: dict[int, int] | None,
    anonymous_group_membership: dict[int, UserGroupMembersData],
) -> NeverSubscribedStreamDict:
    is_archived = raw_stream_dict["deactivated"]
    creator_id = raw_stream_dict["creator_id"]
    date_created = datetime_to_timestamp(raw_stream_dict["date_created"])
    description = raw_stream_dict["description"]
    first_message_id = raw_stream_dict["first_message_id"]
    folder_id = raw_stream_dict["folder_id"]
    is_recently_active = raw_stream_dict["is_recently_active"]
    history_public_to_subscribers = raw_stream_dict["history_public_to_subscribers"]
    invite_only = raw_stream_dict["invite_only"]
    is_web_public = raw_stream_dict["is_web_public"]
    message_retention_days = raw_stream_dict["message_retention_days"]
    name = raw_stream_dict["name"]
    rendered_description = raw_stream_dict["rendered_description"]
    stream_id = raw_stream_dict["id"]
    stream_post_policy = raw_stream_dict["stream_post_policy"]
    subscriber_count = raw_stream_dict["subscriber_count"]
    topics_policy = raw_stream_dict["topics_policy"]

    if recent_traffic is not None:
        stream_weekly_traffic = get_average_weekly_stream_traffic(
            raw_stream_dict["id"], raw_stream_dict["date_created"], recent_traffic
        )
    else:  # nocoverage
        stream_weekly_traffic = None

    can_add_subscribers_group_value = get_group_setting_value_for_register_api(
        raw_stream_dict["can_add_subscribers_group_id"], anonymous_group_membership
    )
    can_administer_channel_group_value = get_group_setting_value_for_register_api(
        raw_stream_dict["can_administer_channel_group_id"], anonymous_group_membership
    )
    can_create_topic_group = get_group_setting_value_for_register_api(
        raw_stream_dict["can_create_topic_group_id"], anonymous_group_membership
    )
    can_delete_any_message_group_value = get_group_setting_value_for_register_api(
        raw_stream_dict["can_delete_any_message_group_id"], anonymous_group_membership
    )
    can_delete_own_message_group_value = get_group_setting_value_for_register_api(
        raw_stream_dict["can_delete_own_message_group_id"], anonymous_group_membership
    )
    can_move_messages_out_of_channel_group_value = get_group_setting_value_for_register_api(
        raw_stream_dict["can_move_messages_out_of_channel_group_id"], anonymous_group_membership
    )
    can_move_messages_within_channel_group_value = get_group_setting_value_for_register_api(
        raw_stream_dict["can_move_messages_within_channel_group_id"], anonymous_group_membership
    )
    can_send_message_group_value = get_group_setting_value_for_register_api(
        raw_stream_dict["can_send_message_group_id"], anonymous_group_membership
    )
    can_remove_subscribers_group_value = get_group_setting_value_for_register_api(
        raw_stream_dict["can_remove_subscribers_group_id"], anonymous_group_membership
    )
    can_resolve_topics_group_value = get_group_setting_value_for_register_api(
        raw_stream_dict["can_resolve_topics_group_id"], anonymous_group_membership
    )
    can_subscribe_group_value = get_group_setting_value_for_register_api(
        raw_stream_dict["can_subscribe_group_id"], anonymous_group_membership
    )

    # Backwards-compatibility addition of removed field.
    is_announcement_only = raw_stream_dict["stream_post_policy"] == Stream.STREAM_POST_POLICY_ADMINS

    # Our caller may add a subscribers field.
    return NeverSubscribedStreamDict(
        is_archived=is_archived,
        can_add_subscribers_group=can_add_subscribers_group_value,
        can_administer_channel_group=can_administer_channel_group_value,
        can_create_topic_group=can_create_topic_group,
        can_delete_any_message_group=can_delete_any_message_group_value,
        can_delete_own_message_group=can_delete_own_message_group_value,
        can_move_messages_out_of_channel_group=can_move_messages_out_of_channel_group_value,
        can_move_messages_within_channel_group=can_move_messages_within_channel_group_value,
        can_send_message_group=can_send_message_group_value,
        can_remove_subscribers_group=can_remove_subscribers_group_value,
        can_resolve_topics_group=can_resolve_topics_group_value,
        can_subscribe_group=can_subscribe_group_value,
        creator_id=creator_id,
        date_created=date_created,
        description=description,
        first_message_id=first_message_id,
        folder_id=folder_id,
        is_recently_active=is_recently_active,
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
        subscriber_count=subscriber_count,
        topics_policy=topics_policy,
    )


def validate_user_access_to_subscribers(user_profile: UserProfile | None, stream: Stream) -> None:
    """Validates whether the user can view the subscribers of a stream.  Raises a JsonableError if:
    * The user and the stream are in different realms
    * The realm is MIT and the stream is not invite only.
    * The stream is invite only, requesting_user is passed, and that user
      does not subscribe to the stream.
    """
    user_group_membership_details = UserGroupMembershipDetails(user_recursive_group_ids=None)
    validate_user_access_to_subscribers_helper(
        user_profile,
        {
            "realm_id": stream.realm_id,
            "is_web_public": stream.is_web_public,
            "invite_only": stream.invite_only,
            "can_administer_channel_group_id": stream.can_administer_channel_group_id,
            "can_add_subscribers_group_id": stream.can_add_subscribers_group_id,
            "can_subscribe_group_id": stream.can_subscribe_group_id,
        },
        # We use a lambda here so that we only compute whether the
        # user is subscribed if we have to
        lambda user_profile: subscribed_to_stream(user_profile, stream.id),
        user_group_membership_details=user_group_membership_details,
    )


def validate_user_access_to_subscribers_helper(
    user_profile: UserProfile | None,
    stream_dict: Mapping[str, Any],
    check_user_subscribed: Callable[[UserProfile], bool],
    user_group_membership_details: UserGroupMembershipDetails,
) -> None:
    """Helper for validate_user_access_to_subscribers that doesn't require
    a full stream object.  This function is a bit hard to read,
    because it is carefully optimized for performance in the two code
    paths we call it from:

    * In `bulk_get_subscriber_user_ids`, we already know whether the
    user was subscribed via `sub_dict`, and so we want to avoid a
    database query at all (especially since it calls this in a loop);
    * In `validate_user_access_to_subscribers`, we want to only check
    if the user is subscribed when we absolutely have to, since it
    costs a database query.

    The `check_user_subscribed` argument is a function that reports
    whether the user is subscribed to the stream.

    Note also that we raise a ValidationError in cases where the
    caller is doing the wrong thing (maybe these should be
    AssertionErrors), and JsonableError for 400 type errors.
    """
    if user_profile is None:
        raise ValidationError("Missing user to validate access for")

    if user_profile.realm_id != stream_dict["realm_id"]:
        raise ValidationError("Requesting user not in given realm")

    # Even guest users can access subscribers to web-public streams,
    # since they can freely become subscribers to these streams.
    if stream_dict["is_web_public"]:
        return

    # With the exception of web-public streams, a guest must
    # be subscribed to a stream (even a public one) in order
    # to see subscribers.
    if user_profile.is_guest and check_user_subscribed(user_profile):
        return
        # We could explicitly handle the case where guests aren't
        # subscribed here in an `else` statement or we can fall
        # through to the subsequent logic.  Tim prefers the latter.
        # Adding an `else` would ensure better code coverage.

    if not user_profile.can_access_public_streams() and not stream_dict["invite_only"]:
        raise JsonableError(_("Subscriber data is not available for this channel"))

    # Organization administrators can view subscribers for all streams.
    if user_profile.is_realm_admin:
        return

    if user_group_membership_details.user_recursive_group_ids is None:
        user_group_membership_details.user_recursive_group_ids = set(
            get_recursive_membership_groups(user_profile).values_list("id", flat=True)
        )

    if has_metadata_access_to_channel_via_groups(
        user_profile,
        user_group_membership_details.user_recursive_group_ids,
        stream_dict["can_administer_channel_group_id"],
        stream_dict["can_add_subscribers_group_id"],
        stream_dict["can_subscribe_group_id"],
    ):
        return

    if stream_dict["invite_only"] and not check_user_subscribed(user_profile):
        raise JsonableError(_("Unable to retrieve subscribers for private channel"))


def bulk_get_subscriber_user_ids(
    stream_dicts: Collection[Mapping[str, Any]],
    user_profile: UserProfile,
    subscribed_stream_ids: set[int],
    streams_to_partially_fetch: list[int],
) -> dict[int, list[int]]:
    """sub_dict maps stream_id => whether the user is subscribed to that stream."""
    target_stream_dicts = []
    is_subscribed: bool
    check_user_subscribed = lambda user_profile: is_subscribed

    user_group_membership_details = UserGroupMembershipDetails(user_recursive_group_ids=None)
    for stream_dict in stream_dicts:
        stream_id = stream_dict["id"]
        is_subscribed = stream_id in subscribed_stream_ids

        try:
            validate_user_access_to_subscribers_helper(
                user_profile,
                stream_dict,
                check_user_subscribed,
                user_group_membership_details,
            )
        except JsonableError:
            continue
        target_stream_dicts.append(stream_dict)

    recip_to_stream_id = {stream["recipient_id"]: stream["id"] for stream in target_stream_dicts}
    full_fetch_recipient_ids = sorted(
        stream["recipient_id"]
        for stream in target_stream_dicts
        if stream["id"] not in streams_to_partially_fetch
    )
    partial_fetch_recipient_ids = sorted(
        stream["recipient_id"]
        for stream in target_stream_dicts
        if stream["id"] in streams_to_partially_fetch
    )

    result: dict[int, list[int]] = {stream["id"]: [] for stream in stream_dicts}
    if not full_fetch_recipient_ids and not partial_fetch_recipient_ids:
        return result

    """
    The raw SQL below leads to more than a 2x speedup when tested with
    20k+ total subscribers.  (For large realms with lots of default
    streams, this function deals with LOTS of data, so it is important
    to optimize.)

    One optimization is to use two branches for creating this query,
    to avoid joining on zerver_userprofile when we're not sending
    partial users.
    """

    if partial_fetch_recipient_ids:
        query = SQL(
            """
            SELECT
                zerver_subscription.recipient_id,
                zerver_subscription.user_profile_id
            FROM
                zerver_subscription
            JOIN zerver_userprofile on zerver_userprofile.id = zerver_subscription.user_profile_id
            WHERE
                zerver_subscription.active AND
                zerver_subscription.is_user_active AND
                (
                    zerver_subscription.recipient_id = ANY (%(full_fetch_recipient_ids)s)
                    OR
                    (
                        zerver_subscription.recipient_id = ANY (%(partial_fetch_recipient_ids)s) AND
                        (zerver_userprofile.is_bot OR (NOT zerver_userprofile.long_term_idle))
                    )
                )
            ORDER BY
                zerver_subscription.recipient_id,
                zerver_subscription.user_profile_id
            """
        )
    else:
        query = SQL(
            """
            SELECT
                zerver_subscription.recipient_id,
                zerver_subscription.user_profile_id
            FROM
                zerver_subscription
            WHERE
                zerver_subscription.active AND
                zerver_subscription.is_user_active AND
                zerver_subscription.recipient_id = ANY (%(full_fetch_recipient_ids)s)
            ORDER BY
                zerver_subscription.recipient_id,
                zerver_subscription.user_profile_id
            """
        )

    cursor = connection.cursor()
    cursor.execute(
        query,
        {
            "full_fetch_recipient_ids": full_fetch_recipient_ids,
            "partial_fetch_recipient_ids": partial_fetch_recipient_ids,
        },
    )
    rows = cursor.fetchall()
    cursor.close()

    """
    Using groupby/itemgetter here is important for performance, at scale.
    It makes it so that all interpreter overhead is just O(N) in nature.
    """
    for recip_id, recip_rows in itertools.groupby(rows, itemgetter(0)):
        user_profile_ids = [r[1] for r in recip_rows]
        stream_id = recip_to_stream_id[recip_id]
        result[stream_id] = list(user_profile_ids)

    return result


def get_subscribers_query(
    stream: Stream, requesting_user: UserProfile | None
) -> QuerySet[Subscription]:
    """Build a query to get the subscribers list for a stream, raising a JsonableError if:

    'realm' is optional in stream.

    The caller can refine this query with select_related(), values(), etc. depending
    on whether it wants objects or just certain fields
    """
    validate_user_access_to_subscribers(requesting_user, stream)

    return get_active_subscriptions_for_stream_id(stream.id, include_deactivated_users=False)


def bulk_get_subscriber_peer_info(
    realm: Realm,
    streams: Collection[Stream] | QuerySet[Stream],
    users_with_metadata_access_via_permission_groups: dict[int, set[int]] | None = None,
) -> SubscriberPeerInfo:
    """
    Glossary:

        subscribed_ids:
            This shows the users who are actually subscribed to the
            stream, which we generally send to the person subscribing
            to the stream.

        private_peer_dict:
            These are the folks that need to know about a new subscriber.
            It's usually a superset of the subscribers.

            Note that we only compute this for PRIVATE streams.  We
            let other code handle peers for public streams, since the
            peers for all public streams are actually the same group
            of users, and downstream code can use that property of
            public streams to avoid extra work.
    """

    subscribed_ids = {}
    private_peer_dict = {}

    private_streams = {stream for stream in streams if stream.invite_only}
    private_stream_ids = {stream.id for stream in private_streams}
    public_stream_ids = {stream.id for stream in streams if not stream.invite_only}

    stream_user_ids = get_user_ids_for_streams(private_stream_ids | public_stream_ids)

    if private_streams:
        realm_admin_ids = {user.id for user in realm.get_admin_users_and_bots()}

        if users_with_metadata_access_via_permission_groups is None:
            users_with_metadata_access_via_permission_groups = (
                get_users_dict_with_metadata_access_to_streams_via_permission_groups(
                    list(private_streams), realm.id
                )
            )

        for stream in private_streams:
            # Realm admins can see all private stream
            # subscribers.
            subscribed_user_ids = stream_user_ids.get(stream.id, set())
            subscribed_ids[stream.id] = subscribed_user_ids
            private_peer_dict[stream.id] = (
                subscribed_user_ids
                | realm_admin_ids
                | users_with_metadata_access_via_permission_groups[stream.id]
            )

    for stream_id in public_stream_ids:
        subscribed_user_ids = stream_user_ids.get(stream_id, set())
        subscribed_ids[stream_id] = subscribed_user_ids

    return SubscriberPeerInfo(
        subscribed_ids=subscribed_ids,
        private_peer_dict=private_peer_dict,
    )


def has_metadata_access_to_previously_subscribed_stream(
    user_profile: UserProfile,
    stream_dict: SubscriptionStreamDict,
    user_recursive_group_ids: set[int],
    can_administer_channel_group_id: int,
    can_add_subscribers_group_id: int,
    can_subscribe_group_id: int,
) -> bool:
    if stream_dict["is_web_public"]:
        return True

    if not user_profile.can_access_public_streams():
        return False

    if stream_dict["invite_only"]:
        return user_profile.is_realm_admin or has_metadata_access_to_channel_via_groups(
            user_profile,
            user_recursive_group_ids,
            can_administer_channel_group_id,
            can_add_subscribers_group_id,
            can_subscribe_group_id,
        )

    return True


# In general, it's better to avoid using .values() because it makes
# the code pretty ugly, but in this case, it has significant
# performance impact for loading / for users with large numbers of
# subscriptions, so it's worth optimizing.
def gather_subscriptions_helper(
    user_profile: UserProfile,
    include_subscribers: bool | Literal["partial"] = True,
    include_archived_channels: bool = False,
    anonymous_group_membership: dict[int, UserGroupMembersData] | None = None,
) -> SubscriptionInfo:
    realm = user_profile.realm
    all_streams = get_all_streams(
        realm, include_archived_channels=include_archived_channels
    ).select_related("can_send_message_group", "can_send_message_group__named_user_group")

    all_stream_dicts = all_streams.values(
        *Stream.API_FIELDS,
        # The realm_id and recipient_id are generally not needed in the API.
        "realm_id",
        "recipient_id",
    )
    recip_id_to_stream_id: dict[int, int] = {
        stream["recipient_id"]: stream["id"] for stream in all_stream_dicts
    }
    all_streams_map: dict[int, RawStreamDict] = {
        stream["id"]: stream for stream in all_stream_dicts
    }

    for stream in all_streams:
        stream_post_policy = get_stream_post_policy_value_based_on_group_setting(
            stream.can_send_message_group
        )
        all_streams_map[stream.id]["stream_post_policy"] = stream_post_policy
        all_streams_map[stream.id]["topics_policy"] = StreamTopicsPolicyEnum(
            stream.topics_policy
        ).name

    if anonymous_group_membership is None:
        setting_group_ids = set()
        for stream_dict in all_stream_dicts:
            for setting_name in Stream.stream_permission_group_settings:
                setting_group_ids.add(stream_dict[setting_name + "_id"])
        anonymous_group_ids = UserGroup.objects.filter(
            id__in=setting_group_ids, named_user_group=None
        ).values_list("id", flat=True)
        anonymous_group_membership = get_members_and_subgroups_of_groups(set(anonymous_group_ids))

    sub_dicts_query: Iterable[RawSubscriptionDict] = (
        get_stream_subscriptions_for_user(user_profile)
        .values(
            *Subscription.API_FIELDS,
            "recipient_id",
            "active",
        )
        .order_by("recipient_id")
    )

    # We only care about subscriptions for active streams.
    sub_dicts: list[RawSubscriptionDict] = [
        sub_dict
        for sub_dict in sub_dicts_query
        if recip_id_to_stream_id.get(sub_dict["recipient_id"])
    ]

    def get_stream_id(sub_dict: RawSubscriptionDict) -> int:
        return recip_id_to_stream_id[sub_dict["recipient_id"]]

    recent_traffic = get_streams_traffic(realm=realm)

    # Okay, now we finally get to populating our main results, which
    # will be these three lists.
    subscribed: list[SubscriptionStreamDict] = []
    unsubscribed: list[SubscriptionStreamDict] = []
    never_subscribed: list[NeverSubscribedStreamDict] = []

    user_recursive_group_ids = set()
    # Optimization for the organization administrator code path. We
    # don't explicitly grant realm admins this permission, but admins
    # implicitly have the can_administer_channel_group permission for
    # all channels. user_recursive_group_ids is used to check the
    # membership of the current user in can_administer_channel_group
    # which we don't need to calculate in case of a realm admin.
    if not user_profile.is_realm_admin:
        user_recursive_group_ids = set(
            get_recursive_membership_groups(user_profile).values_list("id", flat=True)
        )
    sub_unsub_stream_ids = set()
    for sub_dict in sub_dicts:
        stream_id = get_stream_id(sub_dict)
        sub_unsub_stream_ids.add(stream_id)
        raw_stream_dict = all_streams_map[stream_id]
        stream_api_dict = build_stream_api_dict(
            raw_stream_dict, recent_traffic, anonymous_group_membership
        )
        stream_dict = build_stream_dict_for_sub(
            user=user_profile,
            sub_dict=sub_dict,
            stream_dict=stream_api_dict,
        )

        # is_active is represented in this structure by which list we include it in.
        is_active = sub_dict["active"]
        if is_active:
            subscribed.append(stream_dict)
        else:
            can_administer_channel_group_id = raw_stream_dict["can_administer_channel_group_id"]
            can_add_subscribers_group_id = raw_stream_dict["can_add_subscribers_group_id"]
            can_subscribe_group_id = raw_stream_dict["can_subscribe_group_id"]
            if has_metadata_access_to_previously_subscribed_stream(
                user_profile,
                stream_dict,
                user_recursive_group_ids,
                can_administer_channel_group_id,
                can_add_subscribers_group_id,
                can_subscribe_group_id,
            ):
                """
                User who are no longer subscribed to a stream that they don't have
                metadata access to will not receive metadata related to this stream
                and their clients will see it as an unknown stream if referenced
                somewhere (e.g. a markdown stream link), just like they would see
                a reference to a private stream they had never been subscribed to.
                """
                unsubscribed.append(stream_dict)

    if user_profile.can_access_public_streams():
        never_subscribed_stream_ids = set(all_streams_map) - sub_unsub_stream_ids
    else:
        web_public_stream_ids = {
            stream["id"] for stream in all_stream_dicts if stream["is_web_public"]
        }
        never_subscribed_stream_ids = web_public_stream_ids - sub_unsub_stream_ids

    never_subscribed_streams = [
        all_streams_map[stream_id] for stream_id in never_subscribed_stream_ids
    ]

    for raw_stream_dict in never_subscribed_streams:
        is_public = not raw_stream_dict["invite_only"]
        can_administer_channel_group_id = raw_stream_dict["can_administer_channel_group_id"]
        can_add_subscribers_group_id = raw_stream_dict["can_add_subscribers_group_id"]
        can_subscribe_group_id = raw_stream_dict["can_subscribe_group_id"]
        has_metadata_access = has_metadata_access_to_channel_via_groups(
            user_profile,
            user_recursive_group_ids,
            can_administer_channel_group_id,
            can_add_subscribers_group_id,
            can_subscribe_group_id,
        )
        if is_public or user_profile.is_realm_admin or has_metadata_access:
            slim_stream_dict = build_stream_dict_for_never_sub(
                raw_stream_dict=raw_stream_dict,
                recent_traffic=recent_traffic,
                anonymous_group_membership=anonymous_group_membership,
            )

            never_subscribed.append(slim_stream_dict)

    if include_subscribers:
        # The highly optimized bulk_get_subscriber_user_ids wants to know which
        # streams we are subscribed to, for validation purposes, and it uses that
        # info to know if it's allowed to find OTHER subscribers.
        subscribed_stream_ids = {
            get_stream_id(sub_dict) for sub_dict in sub_dicts if sub_dict["active"]
        }

        # If the client only wants partial subscriber data, we send:
        # - all subscribers (full data) for channels with fewer than
        #   MIN_PARTIAL_SUBSCRIBERS_CHANNEL_SIZE subscribers.
        # - only bots and recently active users for other channels.
        streams_to_partially_fetch = []
        if include_subscribers == "partial":
            streams_to_partially_fetch = [
                stream.id
                for stream in all_streams
                if stream.subscriber_count >= settings.MIN_PARTIAL_SUBSCRIBERS_CHANNEL_SIZE
            ]

        subscriber_map = bulk_get_subscriber_user_ids(
            all_stream_dicts,
            user_profile,
            subscribed_stream_ids,
            streams_to_partially_fetch,
        )

        for lst in [subscribed, unsubscribed]:
            for stream_dict in lst:
                assert isinstance(stream_dict["stream_id"], int)
                stream_id = stream_dict["stream_id"]
                if stream_id in streams_to_partially_fetch:
                    stream_dict["partial_subscribers"] = subscriber_map[stream_id]
                else:
                    stream_dict["subscribers"] = subscriber_map[stream_id]

        for slim_stream_dict in never_subscribed:
            assert isinstance(slim_stream_dict["stream_id"], int)
            stream_id = slim_stream_dict["stream_id"]
            if stream_id in streams_to_partially_fetch:
                slim_stream_dict["partial_subscribers"] = subscriber_map[stream_id]
            else:
                slim_stream_dict["subscribers"] = subscriber_map[stream_id]

    subscribed.sort(key=lambda x: x["name"])
    unsubscribed.sort(key=lambda x: x["name"])
    never_subscribed.sort(key=lambda x: x["name"])

    return SubscriptionInfo(
        subscriptions=subscribed,
        unsubscribed=unsubscribed,
        never_subscribed=never_subscribed,
    )


def gather_subscriptions(
    user_profile: UserProfile,
    include_subscribers: bool | Literal["partial"] = False,
) -> tuple[list[SubscriptionStreamDict], list[SubscriptionStreamDict]]:
    helper_result = gather_subscriptions_helper(
        user_profile,
        include_subscribers=include_subscribers,
    )
    subscribed = helper_result.subscriptions
    unsubscribed = helper_result.unsubscribed
    return (subscribed, unsubscribed)
