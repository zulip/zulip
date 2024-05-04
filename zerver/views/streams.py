import time
from collections import defaultdict
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, Union

import orjson
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language

from zerver.actions.default_streams import (
    do_add_default_stream,
    do_add_streams_to_default_stream_group,
    do_change_default_stream_group_description,
    do_change_default_stream_group_name,
    do_create_default_stream_group,
    do_remove_default_stream,
    do_remove_default_stream_group,
    do_remove_streams_from_default_stream_group,
)
from zerver.actions.message_delete import do_delete_messages
from zerver.actions.message_send import (
    do_send_messages,
    internal_prep_private_message,
    internal_prep_stream_message,
)
from zerver.actions.streams import (
    bulk_add_subscriptions,
    bulk_remove_subscriptions,
    do_change_stream_description,
    do_change_stream_group_based_setting,
    do_change_stream_message_retention_days,
    do_change_stream_permission,
    do_change_stream_post_policy,
    do_change_subscription_property,
    do_deactivate_stream,
    do_rename_stream,
    get_subscriber_ids,
)
from zerver.context_processors import get_valid_realm_from_request
from zerver.decorator import require_non_guest_user, require_realm_admin
from zerver.lib.default_streams import get_default_stream_ids_for_realm
from zerver.lib.email_mirror_helpers import encode_email_address
from zerver.lib.exceptions import JsonableError, OrganizationOwnerRequiredError
from zerver.lib.mention import MentionBackend, silent_mention_syntax_for_user
from zerver.lib.message import bulk_access_stream_messages_query
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.retention import STREAM_MESSAGE_BATCH_SIZE as RETENTION_STREAM_MESSAGE_BATCH_SIZE
from zerver.lib.retention import parse_message_retention_days
from zerver.lib.stream_traffic import get_streams_traffic
from zerver.lib.streams import (
    StreamDict,
    access_default_stream_group_by_id,
    access_stream_by_id,
    access_stream_by_name,
    access_stream_for_delete_or_update,
    access_web_public_stream,
    check_stream_name_available,
    do_get_streams,
    filter_stream_authorization,
    get_stream_permission_policy_name,
    list_to_streams,
    stream_to_dict,
)
from zerver.lib.subscription_info import gather_subscriptions
from zerver.lib.topic import (
    get_topic_history_for_public_stream,
    get_topic_history_for_stream,
    messages_for_topic,
)
from zerver.lib.types import Validator
from zerver.lib.user_groups import access_user_group_for_setting
from zerver.lib.users import access_user_by_email, access_user_by_id
from zerver.lib.utils import assert_is_not_none
from zerver.lib.validator import (
    check_bool,
    check_capped_string,
    check_color,
    check_dict,
    check_dict_only,
    check_int,
    check_int_in,
    check_list,
    check_string,
    check_string_or_int,
    check_union,
    to_non_negative_int,
)
from zerver.models import NamedUserGroup, Realm, Stream, UserProfile
from zerver.models.users import get_system_bot


def principal_to_user_profile(agent: UserProfile, principal: Union[str, int]) -> UserProfile:
    if isinstance(principal, str):
        return access_user_by_email(
            agent, principal, allow_deactivated=False, allow_bots=True, for_admin=False
        )
    else:
        return access_user_by_id(
            agent, principal, allow_deactivated=False, allow_bots=True, for_admin=False
        )


def user_directly_controls_user(user_profile: UserProfile, target: UserProfile) -> bool:
    """Returns whether the target user is either the current user or a bot
    owned by the current user"""
    if user_profile == target:
        return True
    if target.is_bot and target.bot_owner_id == user_profile.id:
        return True
    return False


def deactivate_stream_backend(
    request: HttpRequest, user_profile: UserProfile, stream_id: int
) -> HttpResponse:
    (stream, sub) = access_stream_for_delete_or_update(user_profile, stream_id)
    do_deactivate_stream(stream, acting_user=user_profile)
    return json_success(request)


@require_realm_admin
@has_request_variables
def add_default_stream(
    request: HttpRequest, user_profile: UserProfile, stream_id: int = REQ(json_validator=check_int)
) -> HttpResponse:
    (stream, sub) = access_stream_by_id(user_profile, stream_id)
    if stream.invite_only:
        raise JsonableError(_("Private channels cannot be made default."))
    do_add_default_stream(stream)
    return json_success(request)


@require_realm_admin
@has_request_variables
def create_default_stream_group(
    request: HttpRequest,
    user_profile: UserProfile,
    group_name: str = REQ(),
    description: str = REQ(),
    stream_names: List[str] = REQ(json_validator=check_list(check_string)),
) -> HttpResponse:
    streams = []
    for stream_name in stream_names:
        (stream, sub) = access_stream_by_name(user_profile, stream_name)
        streams.append(stream)
    do_create_default_stream_group(user_profile.realm, group_name, description, streams)
    return json_success(request)


@require_realm_admin
@has_request_variables
def update_default_stream_group_info(
    request: HttpRequest,
    user_profile: UserProfile,
    group_id: int,
    new_group_name: Optional[str] = REQ(default=None),
    new_description: Optional[str] = REQ(default=None),
) -> HttpResponse:
    if not new_group_name and not new_description:
        raise JsonableError(_('You must pass "new_description" or "new_group_name".'))

    group = access_default_stream_group_by_id(user_profile.realm, group_id)
    if new_group_name is not None:
        do_change_default_stream_group_name(user_profile.realm, group, new_group_name)
    if new_description is not None:
        do_change_default_stream_group_description(user_profile.realm, group, new_description)
    return json_success(request)


@require_realm_admin
@has_request_variables
def update_default_stream_group_streams(
    request: HttpRequest,
    user_profile: UserProfile,
    group_id: int,
    op: str = REQ(),
    stream_names: List[str] = REQ(json_validator=check_list(check_string)),
) -> HttpResponse:
    group = access_default_stream_group_by_id(user_profile.realm, group_id)
    streams = []
    for stream_name in stream_names:
        (stream, sub) = access_stream_by_name(user_profile, stream_name)
        streams.append(stream)

    if op == "add":
        do_add_streams_to_default_stream_group(user_profile.realm, group, streams)
    elif op == "remove":
        do_remove_streams_from_default_stream_group(user_profile.realm, group, streams)
    else:
        raise JsonableError(_('Invalid value for "op". Specify one of "add" or "remove".'))
    return json_success(request)


@require_realm_admin
@has_request_variables
def remove_default_stream_group(
    request: HttpRequest, user_profile: UserProfile, group_id: int
) -> HttpResponse:
    group = access_default_stream_group_by_id(user_profile.realm, group_id)
    do_remove_default_stream_group(user_profile.realm, group)
    return json_success(request)


@require_realm_admin
@has_request_variables
def remove_default_stream(
    request: HttpRequest, user_profile: UserProfile, stream_id: int = REQ(json_validator=check_int)
) -> HttpResponse:
    (stream, sub) = access_stream_by_id(
        user_profile,
        stream_id,
        allow_realm_admin=True,
    )
    do_remove_default_stream(stream)
    return json_success(request)


@has_request_variables
def update_stream_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    stream_id: int,
    description: Optional[str] = REQ(
        str_validator=check_capped_string(Stream.MAX_DESCRIPTION_LENGTH), default=None
    ),
    is_private: Optional[bool] = REQ(json_validator=check_bool, default=None),
    is_announcement_only: Optional[bool] = REQ(json_validator=check_bool, default=None),
    is_default_stream: Optional[bool] = REQ(json_validator=check_bool, default=None),
    stream_post_policy: Optional[int] = REQ(
        json_validator=check_int_in(Stream.STREAM_POST_POLICY_TYPES), default=None
    ),
    history_public_to_subscribers: Optional[bool] = REQ(json_validator=check_bool, default=None),
    is_web_public: Optional[bool] = REQ(json_validator=check_bool, default=None),
    new_name: Optional[str] = REQ(default=None),
    message_retention_days: Optional[Union[int, str]] = REQ(
        json_validator=check_string_or_int, default=None
    ),
    can_remove_subscribers_group_id: Optional[int] = REQ(
        "can_remove_subscribers_group", json_validator=check_int, default=None
    ),
) -> HttpResponse:
    # We allow realm administrators to to update the stream name and
    # description even for private streams.
    (stream, sub) = access_stream_for_delete_or_update(user_profile, stream_id)

    # Validate that the proposed state for permissions settings is permitted.
    if is_private is not None:
        proposed_is_private = is_private
    else:
        proposed_is_private = stream.invite_only

    if is_web_public is not None:
        proposed_is_web_public = is_web_public
    else:
        proposed_is_web_public = stream.is_web_public

    if is_default_stream is not None:
        proposed_is_default_stream = is_default_stream
    else:
        default_stream_ids = get_default_stream_ids_for_realm(stream.realm_id)
        proposed_is_default_stream = stream.id in default_stream_ids

    if stream.realm.is_zephyr_mirror_realm:
        # In the Zephyr mirroring model, history is unconditionally
        # not public to subscribers, even for public streams.
        proposed_history_public_to_subscribers = False
    elif history_public_to_subscribers is not None:
        proposed_history_public_to_subscribers = history_public_to_subscribers
    elif is_private is not None:
        # By default, private streams have protected history while for
        # public streams history is public by default.
        proposed_history_public_to_subscribers = not is_private
    else:
        proposed_history_public_to_subscribers = stream.history_public_to_subscribers

    # Web-public streams must have subscriber-public history.
    if proposed_is_web_public and not proposed_history_public_to_subscribers:
        raise JsonableError(_("Invalid parameters"))

    # Web-public streams must not be private.
    if proposed_is_web_public and proposed_is_private:
        raise JsonableError(_("Invalid parameters"))

    # Public streams must be public to subscribers.
    if not proposed_is_private and not proposed_history_public_to_subscribers:
        if stream.realm.is_zephyr_mirror_realm:
            # All Zephyr realm streams violate this rule.
            pass
        else:
            raise JsonableError(_("Invalid parameters"))

    # Ensure that a stream cannot be both a default stream for new users and private
    if proposed_is_private and proposed_is_default_stream:
        raise JsonableError(_("A default channel cannot be private."))

    if is_private is not None:
        # We require even realm administrators to be actually
        # subscribed to make a private stream public, via this
        # stricted access_stream check.
        access_stream_by_id(user_profile, stream_id)

    # Enforce restrictions on creating web-public streams. Since these
    # checks are only required when changing a stream to be
    # web-public, we don't use an "is not None" check.
    if is_web_public:
        if not user_profile.realm.web_public_streams_enabled():
            raise JsonableError(_("Web-public channels are not enabled."))
        if not user_profile.can_create_web_public_streams():
            raise JsonableError(_("Insufficient permission"))

    if (
        is_private is not None
        or is_web_public is not None
        or history_public_to_subscribers is not None
    ):
        do_change_stream_permission(
            stream,
            invite_only=proposed_is_private,
            history_public_to_subscribers=proposed_history_public_to_subscribers,
            is_web_public=proposed_is_web_public,
            acting_user=user_profile,
        )

    if is_default_stream is not None:
        if is_default_stream:
            do_add_default_stream(stream)
        else:
            do_remove_default_stream(stream)

    if message_retention_days is not None:
        if not user_profile.is_realm_owner:
            raise OrganizationOwnerRequiredError
        user_profile.realm.ensure_not_on_limited_plan()
        new_message_retention_days_value = parse_message_retention_days(
            message_retention_days, Stream.MESSAGE_RETENTION_SPECIAL_VALUES_MAP
        )
        do_change_stream_message_retention_days(
            stream, user_profile, new_message_retention_days_value
        )

    if description is not None:
        if "\n" in description:
            # We don't allow newline characters in stream descriptions.
            description = description.replace("\n", " ")
        do_change_stream_description(stream, description, acting_user=user_profile)
    if new_name is not None:
        new_name = new_name.strip()
        if stream.name == new_name:
            raise JsonableError(_("Channel already has that name."))
        if stream.name.lower() != new_name.lower():
            # Check that the stream name is available (unless we are
            # are only changing the casing of the stream name).
            check_stream_name_available(user_profile.realm, new_name)
        do_rename_stream(stream, new_name, user_profile)
    if is_announcement_only is not None:
        # is_announcement_only is a legacy way to specify
        # stream_post_policy.  We can probably just delete this code,
        # since we're not aware of clients that used it, but we're
        # keeping it for backwards-compatibility for now.
        stream_post_policy = Stream.STREAM_POST_POLICY_EVERYONE
        if is_announcement_only:
            stream_post_policy = Stream.STREAM_POST_POLICY_ADMINS
    if stream_post_policy is not None:
        do_change_stream_post_policy(stream, stream_post_policy, acting_user=user_profile)

    for setting_name, permission_configuration in Stream.stream_permission_group_settings.items():
        request_settings_dict = locals()
        setting_group_id_name = permission_configuration.id_field_name

        if setting_group_id_name not in request_settings_dict:  # nocoverage
            continue

        if request_settings_dict[setting_group_id_name] is not None and request_settings_dict[
            setting_group_id_name
        ] != getattr(stream, setting_group_id_name):
            if sub is None and stream.invite_only:
                # Admins cannot change this setting for unsubscribed private streams.
                raise JsonableError(_("Invalid channel ID"))

            user_group_id = request_settings_dict[setting_group_id_name]
            user_group = access_user_group_for_setting(
                user_group_id,
                user_profile,
                setting_name=setting_name,
                permission_configuration=permission_configuration,
            )
            do_change_stream_group_based_setting(
                stream, setting_name, user_group, acting_user=user_profile
            )

    return json_success(request)


@has_request_variables
def list_subscriptions_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    include_subscribers: bool = REQ(json_validator=check_bool, default=False),
) -> HttpResponse:
    subscribed, _ = gather_subscriptions(
        user_profile,
        include_subscribers=include_subscribers,
    )
    return json_success(request, data={"subscriptions": subscribed})


add_subscriptions_schema = check_list(
    check_dict_only(
        required_keys=[("name", check_string)],
        optional_keys=[
            ("color", check_color),
            ("description", check_capped_string(Stream.MAX_DESCRIPTION_LENGTH)),
        ],
    ),
)

remove_subscriptions_schema = check_list(check_string)


@has_request_variables
def update_subscriptions_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    delete: Sequence[str] = REQ(json_validator=remove_subscriptions_schema, default=[]),
    add: Sequence[Mapping[str, str]] = REQ(json_validator=add_subscriptions_schema, default=[]),
) -> HttpResponse:
    if not add and not delete:
        raise JsonableError(_('Nothing to do. Specify at least one of "add" or "delete".'))

    thunks = [
        lambda: add_subscriptions_backend(request, user_profile, streams_raw=add),
        lambda: remove_subscriptions_backend(request, user_profile, streams_raw=delete),
    ]
    data = compose_views(thunks)

    return json_success(request, data)


def compose_views(thunks: List[Callable[[], HttpResponse]]) -> Dict[str, Any]:
    """
    This takes a series of thunks and calls them in sequence, and it
    smushes all the json results into a single response when
    everything goes right.  (This helps clients avoid extra latency
    hops.)  It rolls back the transaction when things go wrong in any
    one of the composed methods.
    """

    json_dict: Dict[str, Any] = {}
    with transaction.atomic():
        for thunk in thunks:
            response = thunk()
            json_dict.update(orjson.loads(response.content))
    return json_dict


check_principals: Validator[Union[List[str], List[int]]] = check_union(
    [check_list(check_string), check_list(check_int)],
)


@has_request_variables
def remove_subscriptions_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    streams_raw: Sequence[str] = REQ("subscriptions", json_validator=remove_subscriptions_schema),
    principals: Optional[Union[List[str], List[int]]] = REQ(
        json_validator=check_principals, default=None
    ),
) -> HttpResponse:
    realm = user_profile.realm

    streams_as_dict: List[StreamDict] = [
        {"name": stream_name.strip()} for stream_name in streams_raw
    ]

    unsubscribing_others = False
    if principals:
        people_to_unsub = set()
        for principal in principals:
            target_user = principal_to_user_profile(user_profile, principal)
            people_to_unsub.add(target_user)
            if not user_directly_controls_user(user_profile, target_user):
                unsubscribing_others = True
    else:
        people_to_unsub = {user_profile}

    streams, __ = list_to_streams(
        streams_as_dict,
        user_profile,
        unsubscribing_others=unsubscribing_others,
    )

    result: Dict[str, List[str]] = dict(removed=[], not_removed=[])
    (removed, not_subscribed) = bulk_remove_subscriptions(
        realm, people_to_unsub, streams, acting_user=user_profile
    )

    for subscriber, removed_stream in removed:
        result["removed"].append(removed_stream.name)
    for subscriber, not_subscribed_stream in not_subscribed:
        result["not_removed"].append(not_subscribed_stream.name)

    return json_success(request, data=result)


def you_were_just_subscribed_message(
    acting_user: UserProfile, recipient_user: UserProfile, stream_names: Set[str]
) -> str:
    subscriptions = sorted(stream_names)
    if len(subscriptions) == 1:
        with override_language(recipient_user.default_language):
            return _("{user_full_name} subscribed you to the channel {channel_name}.").format(
                user_full_name=f"@**{acting_user.full_name}|{acting_user.id}**",
                channel_name=f"#**{subscriptions[0]}**",
            )

    with override_language(recipient_user.default_language):
        message = _("{user_full_name} subscribed you to the following channels:").format(
            user_full_name=f"@**{acting_user.full_name}|{acting_user.id}**",
        )
    message += "\n\n"
    for channel_name in subscriptions:
        message += f"* #**{channel_name}**\n"
    return message


RETENTION_DEFAULT: Union[str, int] = "realm_default"
EMPTY_PRINCIPALS: Union[Sequence[str], Sequence[int]] = []


@require_non_guest_user
@has_request_variables
def add_subscriptions_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    streams_raw: Sequence[Mapping[str, str]] = REQ(
        "subscriptions", json_validator=add_subscriptions_schema
    ),
    invite_only: bool = REQ(json_validator=check_bool, default=False),
    is_web_public: bool = REQ(json_validator=check_bool, default=False),
    is_default_stream: bool = REQ(json_validator=check_bool, default=False),
    stream_post_policy: int = REQ(
        json_validator=check_int_in(Stream.STREAM_POST_POLICY_TYPES),
        default=Stream.STREAM_POST_POLICY_EVERYONE,
    ),
    history_public_to_subscribers: Optional[bool] = REQ(json_validator=check_bool, default=None),
    message_retention_days: Union[str, int] = REQ(
        json_validator=check_string_or_int, default=RETENTION_DEFAULT
    ),
    can_remove_subscribers_group_id: Optional[int] = REQ(
        "can_remove_subscribers_group", json_validator=check_int, default=None
    ),
    announce: bool = REQ(json_validator=check_bool, default=False),
    principals: Union[Sequence[str], Sequence[int]] = REQ(
        json_validator=check_principals,
        default=EMPTY_PRINCIPALS,
    ),
    authorization_errors_fatal: bool = REQ(json_validator=check_bool, default=True),
) -> HttpResponse:
    realm = user_profile.realm
    stream_dicts = []
    color_map = {}

    if can_remove_subscribers_group_id is not None:
        permission_configuration = Stream.stream_permission_group_settings[
            "can_remove_subscribers_group"
        ]
        can_remove_subscribers_group = access_user_group_for_setting(
            can_remove_subscribers_group_id,
            user_profile,
            setting_name="can_remove_subscribers_group",
            permission_configuration=permission_configuration,
        )
    else:
        can_remove_subscribers_group_default_name = Stream.stream_permission_group_settings[
            "can_remove_subscribers_group"
        ].default_group_name
        can_remove_subscribers_group = NamedUserGroup.objects.get(
            name=can_remove_subscribers_group_default_name,
            realm=user_profile.realm,
            is_system_group=True,
        )

    for stream_dict in streams_raw:
        # 'color' field is optional
        # check for its presence in the streams_raw first
        if "color" in stream_dict:
            color_map[stream_dict["name"]] = stream_dict["color"]

        stream_dict_copy: StreamDict = {}
        stream_dict_copy["name"] = stream_dict["name"].strip()

        # We don't allow newline characters in stream descriptions.
        if "description" in stream_dict:
            stream_dict_copy["description"] = stream_dict["description"].replace("\n", " ")

        stream_dict_copy["invite_only"] = invite_only
        stream_dict_copy["is_web_public"] = is_web_public
        stream_dict_copy["stream_post_policy"] = stream_post_policy
        stream_dict_copy["history_public_to_subscribers"] = history_public_to_subscribers
        stream_dict_copy["message_retention_days"] = parse_message_retention_days(
            message_retention_days, Stream.MESSAGE_RETENTION_SPECIAL_VALUES_MAP
        )
        stream_dict_copy["can_remove_subscribers_group"] = can_remove_subscribers_group

        stream_dicts.append(stream_dict_copy)

    is_subscribing_other_users = False
    if len(principals) > 0 and not all(user_id == user_profile.id for user_id in principals):
        is_subscribing_other_users = True

    if is_subscribing_other_users:
        if not user_profile.can_subscribe_other_users():
            # Guest users case will not be handled here as it will
            # be handled by the decorator above.
            raise JsonableError(_("Insufficient permission"))
        subscribers = {
            principal_to_user_profile(user_profile, principal) for principal in principals
        }
    else:
        subscribers = {user_profile}

    # Validation of the streams arguments, including enforcement of
    # can_create_streams policy and check_stream_name policy is inside
    # list_to_streams.
    existing_streams, created_streams = list_to_streams(
        stream_dicts, user_profile, autocreate=True, is_default_stream=is_default_stream
    )
    authorized_streams, unauthorized_streams = filter_stream_authorization(
        user_profile, existing_streams
    )
    if len(unauthorized_streams) > 0 and authorization_errors_fatal:
        raise JsonableError(
            _("Unable to access channel ({channel_name}).").format(
                channel_name=unauthorized_streams[0].name,
            )
        )
    # Newly created streams are also authorized for the creator
    streams = authorized_streams + created_streams

    if (
        is_subscribing_other_users
        and realm.is_zephyr_mirror_realm
        and not all(stream.invite_only for stream in streams)
    ):
        raise JsonableError(
            _("You can only invite other Zephyr mirroring users to private channels.")
        )

    if is_default_stream:
        for stream in created_streams:
            do_add_default_stream(stream)

    (subscribed, already_subscribed) = bulk_add_subscriptions(
        realm, streams, subscribers, acting_user=user_profile, color_map=color_map
    )

    # We can assume unique emails here for now, but we should eventually
    # convert this function to be more id-centric.
    email_to_user_profile: Dict[str, UserProfile] = {}

    result: Dict[str, Any] = dict(
        subscribed=defaultdict(list), already_subscribed=defaultdict(list)
    )
    for sub_info in subscribed:
        subscriber = sub_info.user
        stream = sub_info.stream
        result["subscribed"][subscriber.email].append(stream.name)
        email_to_user_profile[subscriber.email] = subscriber
    for sub_info in already_subscribed:
        subscriber = sub_info.user
        stream = sub_info.stream
        result["already_subscribed"][subscriber.email].append(stream.name)

    result["subscribed"] = dict(result["subscribed"])
    result["already_subscribed"] = dict(result["already_subscribed"])

    send_messages_for_new_subscribers(
        user_profile=user_profile,
        subscribers=subscribers,
        new_subscriptions=result["subscribed"],
        email_to_user_profile=email_to_user_profile,
        created_streams=created_streams,
        announce=announce,
    )

    result["subscribed"] = dict(result["subscribed"])
    result["already_subscribed"] = dict(result["already_subscribed"])
    if not authorization_errors_fatal:
        result["unauthorized"] = [s.name for s in unauthorized_streams]
    return json_success(request, data=result)


def send_messages_for_new_subscribers(
    user_profile: UserProfile,
    subscribers: Set[UserProfile],
    new_subscriptions: Dict[str, List[str]],
    email_to_user_profile: Dict[str, UserProfile],
    created_streams: List[Stream],
    announce: bool,
) -> None:
    """
    If you are subscribing lots of new users to new streams,
    this function can be pretty expensive in terms of generating
    lots of queries and sending lots of messages.  We isolate
    the code partly to make it easier to test things like
    excessive query counts by mocking this function so that it
    doesn't drown out query counts from other code.
    """
    bots = {subscriber.email: subscriber.is_bot for subscriber in subscribers}

    newly_created_stream_names = {s.name for s in created_streams}

    realm = user_profile.realm
    mention_backend = MentionBackend(realm.id)

    # Inform the user if someone else subscribed them to stuff,
    # or if a new stream was created with the "announce" option.
    notifications = []
    if new_subscriptions:
        for email, subscribed_stream_names in new_subscriptions.items():
            if email == user_profile.email:
                # Don't send a Zulip if you invited yourself.
                continue
            if bots[email]:
                # Don't send invitation Zulips to bots
                continue

            # For each user, we notify them about newly subscribed streams, except for
            # streams that were newly created.
            notify_stream_names = set(subscribed_stream_names) - newly_created_stream_names

            if not notify_stream_names:
                continue

            recipient_user = email_to_user_profile[email]
            sender = get_system_bot(settings.NOTIFICATION_BOT, recipient_user.realm_id)

            msg = you_were_just_subscribed_message(
                acting_user=user_profile,
                recipient_user=recipient_user,
                stream_names=notify_stream_names,
            )

            notifications.append(
                internal_prep_private_message(
                    sender=sender,
                    recipient_user=recipient_user,
                    content=msg,
                    mention_backend=mention_backend,
                )
            )

    if announce and len(created_streams) > 0:
        new_stream_announcements_stream = user_profile.realm.get_new_stream_announcements_stream()
        if new_stream_announcements_stream is not None:
            with override_language(new_stream_announcements_stream.realm.default_language):
                if len(created_streams) > 1:
                    content = _("{user_name} created the following channels: {new_channels}.")
                else:
                    content = _("{user_name} created a new channel {new_channels}.")
                topic_name = _("new channels")

            content = content.format(
                user_name=silent_mention_syntax_for_user(user_profile),
                new_channels=", ".join(f"#**{s.name}**" for s in created_streams),
            )

            sender = get_system_bot(
                settings.NOTIFICATION_BOT, new_stream_announcements_stream.realm_id
            )

            notifications.append(
                internal_prep_stream_message(
                    sender=sender,
                    stream=new_stream_announcements_stream,
                    topic_name=topic_name,
                    content=content,
                ),
            )

    if not user_profile.realm.is_zephyr_mirror_realm and len(created_streams) > 0:
        sender = get_system_bot(settings.NOTIFICATION_BOT, user_profile.realm_id)
        for stream in created_streams:
            with override_language(stream.realm.default_language):
                if stream.description == "":
                    stream_description = "*" + _("No description.") + "*"
                else:
                    stream_description = stream.description
                notifications.append(
                    internal_prep_stream_message(
                        sender=sender,
                        stream=stream,
                        topic_name=str(Realm.STREAM_EVENTS_NOTIFICATION_TOPIC_NAME),
                        content=_(
                            "**{policy}** channel created by {user_name}. **Description:**"
                        ).format(
                            user_name=silent_mention_syntax_for_user(user_profile),
                            policy=get_stream_permission_policy_name(
                                invite_only=stream.invite_only,
                                history_public_to_subscribers=stream.history_public_to_subscribers,
                                is_web_public=stream.is_web_public,
                            ),
                        )
                        + f"\n```` quote\n{stream_description}\n````",
                    ),
                )

    if len(notifications) > 0:
        do_send_messages(notifications, mark_as_read=[user_profile.id])


@has_request_variables
def get_subscribers_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    stream_id: int = REQ("stream", converter=to_non_negative_int, path_only=True),
) -> HttpResponse:
    (stream, sub) = access_stream_by_id(
        user_profile,
        stream_id,
        allow_realm_admin=True,
    )
    subscribers = get_subscriber_ids(stream, user_profile)

    return json_success(request, data={"subscribers": list(subscribers)})


# By default, lists all streams that the user has access to --
# i.e. public streams plus invite-only streams that the user is on
@has_request_variables
def get_streams_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    include_public: bool = REQ(json_validator=check_bool, default=True),
    include_web_public: bool = REQ(json_validator=check_bool, default=False),
    include_subscribed: bool = REQ(json_validator=check_bool, default=True),
    include_all_active: bool = REQ(json_validator=check_bool, default=False),
    include_default: bool = REQ(json_validator=check_bool, default=False),
    include_owner_subscribed: bool = REQ(json_validator=check_bool, default=False),
) -> HttpResponse:
    streams = do_get_streams(
        user_profile,
        include_public=include_public,
        include_web_public=include_web_public,
        include_subscribed=include_subscribed,
        include_all_active=include_all_active,
        include_default=include_default,
        include_owner_subscribed=include_owner_subscribed,
    )
    return json_success(request, data={"streams": streams})


@has_request_variables
def get_stream_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    stream_id: int,
) -> HttpResponse:
    (stream, sub) = access_stream_by_id(user_profile, stream_id, allow_realm_admin=True)

    recent_traffic = get_streams_traffic({stream.id}, user_profile.realm)
    return json_success(request, data={"stream": stream_to_dict(stream, recent_traffic)})


@has_request_variables
def get_topics_backend(
    request: HttpRequest,
    maybe_user_profile: Union[UserProfile, AnonymousUser],
    stream_id: int = REQ(converter=to_non_negative_int, path_only=True),
) -> HttpResponse:
    if not maybe_user_profile.is_authenticated:
        is_web_public_query = True
        user_profile: Optional[UserProfile] = None
    else:
        is_web_public_query = False
        assert isinstance(maybe_user_profile, UserProfile)
        user_profile = maybe_user_profile
        assert user_profile is not None

    if is_web_public_query:
        realm = get_valid_realm_from_request(request)
        stream = access_web_public_stream(stream_id, realm)
        result = get_topic_history_for_public_stream(
            realm_id=realm.id, recipient_id=assert_is_not_none(stream.recipient_id)
        )

    else:
        assert user_profile is not None

        (stream, sub) = access_stream_by_id(user_profile, stream_id)

        assert stream.recipient_id is not None
        result = get_topic_history_for_stream(
            user_profile=user_profile,
            recipient_id=stream.recipient_id,
            public_history=stream.is_history_public_to_subscribers(),
        )

    return json_success(request, data=dict(topics=result))


@require_realm_admin
@has_request_variables
def delete_in_topic(
    request: HttpRequest,
    user_profile: UserProfile,
    stream_id: int = REQ(converter=to_non_negative_int, path_only=True),
    topic_name: str = REQ("topic_name"),
) -> HttpResponse:
    stream, ignored_sub = access_stream_by_id(user_profile, stream_id)

    messages = messages_for_topic(
        user_profile.realm_id, assert_is_not_none(stream.recipient_id), topic_name
    )
    # This handles applying access control, such that only messages
    # the user can see are returned in the query.
    messages = bulk_access_stream_messages_query(user_profile, messages, stream)

    # Topics can be large enough that this request will inevitably time out.
    # In such a case, it's good for some progress to be accomplished, so that
    # full deletion can be achieved by repeating the request. For that purpose,
    # we delete messages in atomic batches, committing after each batch.
    # TODO: Ideally this should be moved to the deferred_work queue.
    start_time = time.monotonic()
    batch_size = RETENTION_STREAM_MESSAGE_BATCH_SIZE
    while True:
        if time.monotonic() >= start_time + 50:
            return json_success(request, data={"complete": False})
        with transaction.atomic(durable=True):
            messages_to_delete = messages.order_by("-id")[0:batch_size].select_for_update(
                of=("self",)
            )
            if not messages_to_delete:
                break
            do_delete_messages(user_profile.realm, messages_to_delete)

    return json_success(request, data={"complete": True})


@has_request_variables
def json_get_stream_id(
    request: HttpRequest, user_profile: UserProfile, stream_name: str = REQ("stream")
) -> HttpResponse:
    (stream, sub) = access_stream_by_name(user_profile, stream_name)
    return json_success(request, data={"stream_id": stream.id})


@has_request_variables
def update_subscriptions_property(
    request: HttpRequest,
    user_profile: UserProfile,
    stream_id: int = REQ(json_validator=check_int),
    property: str = REQ(),
    value: str = REQ(),
) -> HttpResponse:
    subscription_data = [{"property": property, "stream_id": stream_id, "value": value}]
    return update_subscription_properties_backend(
        request, user_profile, subscription_data=subscription_data
    )


@has_request_variables
def update_subscription_properties_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    subscription_data: List[Dict[str, Any]] = REQ(
        json_validator=check_list(
            check_dict(
                [
                    ("stream_id", check_int),
                    ("property", check_string),
                    ("value", check_union([check_string, check_bool])),
                ]
            ),
        ),
    ),
) -> HttpResponse:
    """
    This is the entry point to changing subscription properties. This
    is a bulk endpoint: requesters always provide a subscription_data
    list containing dictionaries for each stream of interest.

    Requests are of the form:

    [{"stream_id": "1", "property": "is_muted", "value": False},
     {"stream_id": "1", "property": "color", "value": "#c2c2c2"}]
    """
    property_converters = {
        "color": check_color,
        "in_home_view": check_bool,
        "is_muted": check_bool,
        "desktop_notifications": check_bool,
        "audible_notifications": check_bool,
        "push_notifications": check_bool,
        "email_notifications": check_bool,
        "pin_to_top": check_bool,
        "wildcard_mentions_notify": check_bool,
    }

    for change in subscription_data:
        stream_id = change["stream_id"]
        property = change["property"]
        value = change["value"]

        if property not in property_converters:
            raise JsonableError(
                _("Unknown subscription property: {property}").format(property=property)
            )

        (stream, sub) = access_stream_by_id(user_profile, stream_id)
        if sub is None:
            raise JsonableError(
                _("Not subscribed to channel ID {channel_id}").format(channel_id=stream_id)
            )

        try:
            value = property_converters[property](property, value)
        except ValidationError as error:
            raise JsonableError(error.message)

        do_change_subscription_property(
            user_profile, sub, stream, property, value, acting_user=user_profile
        )

    return json_success(request)


@has_request_variables
def get_stream_email_address(
    request: HttpRequest,
    user_profile: UserProfile,
    stream_id: int = REQ("stream", converter=to_non_negative_int, path_only=True),
) -> HttpResponse:
    (stream, sub) = access_stream_by_id(
        user_profile,
        stream_id,
    )
    stream_email = encode_email_address(stream, show_sender=True)

    return json_success(request, data={"email": stream_email})
