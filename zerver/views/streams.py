from collections import defaultdict
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

import orjson
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.utils.translation import override as override_language
from django.utils.translation import ugettext as _

from zerver.context_processors import get_valid_realm_from_request
from zerver.decorator import (
    authenticated_json_view,
    require_non_guest_user,
    require_post,
    require_realm_admin,
)
from zerver.lib.actions import (
    bulk_add_subscriptions,
    bulk_remove_subscriptions,
    do_add_default_stream,
    do_add_streams_to_default_stream_group,
    do_change_default_stream_group_description,
    do_change_default_stream_group_name,
    do_change_stream_description,
    do_change_stream_invite_only,
    do_change_stream_message_retention_days,
    do_change_stream_post_policy,
    do_change_subscription_property,
    do_create_default_stream_group,
    do_deactivate_stream,
    do_delete_messages,
    do_get_streams,
    do_remove_default_stream,
    do_remove_default_stream_group,
    do_remove_streams_from_default_stream_group,
    do_rename_stream,
    do_send_messages,
    gather_subscriptions,
    get_default_streams_for_realm,
    get_subscriber_emails,
    internal_prep_private_message,
    internal_prep_stream_message,
)
from zerver.lib.exceptions import ErrorCode, JsonableError, OrganizationOwnerRequired
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.retention import parse_message_retention_days
from zerver.lib.streams import (
    StreamDict,
    access_default_stream_group_by_id,
    access_stream_by_id,
    access_stream_by_name,
    access_stream_for_delete_or_update,
    access_web_public_stream,
    check_stream_name,
    check_stream_name_available,
    filter_stream_authorization,
    list_to_streams,
)
from zerver.lib.topic import (
    get_topic_history_for_public_stream,
    get_topic_history_for_stream,
    messages_for_topic,
)
from zerver.lib.types import Validator
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
from zerver.models import (
    Realm,
    Stream,
    UserMessage,
    UserProfile,
    get_active_user,
    get_active_user_profile_by_id_in_realm,
    get_system_bot,
)


class PrincipalError(JsonableError):
    code = ErrorCode.UNAUTHORIZED_PRINCIPAL
    data_fields = ['principal']
    http_status_code = 403

    def __init__(self, principal: Union[int, str]) -> None:
        self.principal: Union[int, str] = principal

    @staticmethod
    def msg_format() -> str:
        return _("User not authorized to execute queries on behalf of '{principal}'")

def principal_to_user_profile(agent: UserProfile, principal: Union[str, int]) -> UserProfile:
    try:
        if isinstance(principal, str):
            return get_active_user(principal, agent.realm)
        else:
            return get_active_user_profile_by_id_in_realm(principal, agent.realm)
    except UserProfile.DoesNotExist:
        # We have to make sure we don't leak information about which users
        # are registered for Zulip in a different realm.  We could do
        # something a little more clever and check the domain part of the
        # principal to maybe give a better error message
        raise PrincipalError(principal)

def check_if_removing_someone_else(user_profile: UserProfile,
                                   principals: Optional[Union[List[str], List[int]]]) -> bool:
    if principals is None or len(principals) == 0:
        return False

    if len(principals) > 1:
        return True

    if isinstance(principals[0], int):
        return principals[0] != user_profile.id
    else:
        return principals[0] != user_profile.email

def deactivate_stream_backend(request: HttpRequest,
                              user_profile: UserProfile,
                              stream_id: int) -> HttpResponse:
    (stream, sub) = access_stream_for_delete_or_update(user_profile, stream_id)
    do_deactivate_stream(stream, acting_user=user_profile)
    return json_success()

@require_realm_admin
@has_request_variables
def add_default_stream(request: HttpRequest,
                       user_profile: UserProfile,
                       stream_id: int=REQ(validator=check_int)) -> HttpResponse:
    (stream, sub) = access_stream_by_id(user_profile, stream_id)
    if stream.invite_only:
        return json_error(_("Private streams cannot be made default."))
    do_add_default_stream(stream)
    return json_success()

@require_realm_admin
@has_request_variables
def create_default_stream_group(request: HttpRequest, user_profile: UserProfile,
                                group_name: str=REQ(), description: str=REQ(),
                                stream_names: List[str]=REQ(validator=check_list(check_string))) -> None:
    streams = []
    for stream_name in stream_names:
        (stream, sub) = access_stream_by_name(user_profile, stream_name)
        streams.append(stream)
    do_create_default_stream_group(user_profile.realm, group_name, description, streams)
    return json_success()

@require_realm_admin
@has_request_variables
def update_default_stream_group_info(request: HttpRequest, user_profile: UserProfile, group_id: int,
                                     new_group_name: Optional[str]=REQ(validator=check_string, default=None),
                                     new_description: Optional[str]=REQ(validator=check_string,
                                                                        default=None)) -> None:
    if not new_group_name and not new_description:
        return json_error(_('You must pass "new_description" or "new_group_name".'))

    group = access_default_stream_group_by_id(user_profile.realm, group_id)
    if new_group_name is not None:
        do_change_default_stream_group_name(user_profile.realm, group, new_group_name)
    if new_description is not None:
        do_change_default_stream_group_description(user_profile.realm, group, new_description)
    return json_success()

@require_realm_admin
@has_request_variables
def update_default_stream_group_streams(request: HttpRequest, user_profile: UserProfile,
                                        group_id: int, op: str=REQ(),
                                        stream_names: List[str]=REQ(
                                            validator=check_list(check_string))) -> None:
    group = access_default_stream_group_by_id(user_profile.realm, group_id)
    streams = []
    for stream_name in stream_names:
        (stream, sub) = access_stream_by_name(user_profile, stream_name)
        streams.append(stream)

    if op == 'add':
        do_add_streams_to_default_stream_group(user_profile.realm, group, streams)
    elif op == 'remove':
        do_remove_streams_from_default_stream_group(user_profile.realm, group, streams)
    else:
        return json_error(_('Invalid value for "op". Specify one of "add" or "remove".'))
    return json_success()

@require_realm_admin
@has_request_variables
def remove_default_stream_group(request: HttpRequest, user_profile: UserProfile,
                                group_id: int) -> None:
    group = access_default_stream_group_by_id(user_profile.realm, group_id)
    do_remove_default_stream_group(user_profile.realm, group)
    return json_success()

@require_realm_admin
@has_request_variables
def remove_default_stream(request: HttpRequest,
                          user_profile: UserProfile,
                          stream_id: int=REQ(validator=check_int)) -> HttpResponse:
    (stream, sub) = access_stream_by_id(
        user_profile,
        stream_id,
        allow_realm_admin=True,
    )
    do_remove_default_stream(stream)
    return json_success()

@has_request_variables
def update_stream_backend(
        request: HttpRequest, user_profile: UserProfile,
        stream_id: int,
        description: Optional[str]=REQ(validator=check_capped_string(
            Stream.MAX_DESCRIPTION_LENGTH), default=None),
        is_private: Optional[bool]=REQ(validator=check_bool, default=None),
        is_announcement_only: Optional[bool]=REQ(validator=check_bool, default=None),
        stream_post_policy: Optional[int]=REQ(validator=check_int_in(
            Stream.STREAM_POST_POLICY_TYPES), default=None),
        history_public_to_subscribers: Optional[bool]=REQ(validator=check_bool, default=None),
        new_name: Optional[str]=REQ(validator=check_string, default=None),
        message_retention_days: Optional[Union[int, str]]=REQ(validator=check_string_or_int, default=None),
) -> HttpResponse:
    # We allow realm administrators to to update the stream name and
    # description even for private streams.
    (stream, sub) = access_stream_for_delete_or_update(user_profile, stream_id)

    if message_retention_days is not None:
        if not user_profile.is_realm_owner:
            raise OrganizationOwnerRequired()
        user_profile.realm.ensure_not_on_limited_plan()
        message_retention_days_value = parse_message_retention_days(
            message_retention_days, Stream.MESSAGE_RETENTION_SPECIAL_VALUES_MAP)
        do_change_stream_message_retention_days(stream, message_retention_days_value)

    if description is not None:
        if '\n' in description:
            # We don't allow newline characters in stream descriptions.
            description = description.replace("\n", " ")
        do_change_stream_description(stream, description)
    if new_name is not None:
        new_name = new_name.strip()
        if stream.name == new_name:
            return json_error(_("Stream already has that name!"))
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
        do_change_stream_post_policy(stream, stream_post_policy)

    # But we require even realm administrators to be actually
    # subscribed to make a private stream public.
    if is_private is not None:
        default_stream_ids = {s.id for s in get_default_streams_for_realm(stream.realm_id)}
        (stream, sub) = access_stream_by_id(user_profile, stream_id)
        if is_private and stream.id in default_stream_ids:
            return json_error(_("Default streams cannot be made private."))
        do_change_stream_invite_only(stream, is_private, history_public_to_subscribers)
    return json_success()

@has_request_variables
def list_subscriptions_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    include_subscribers: bool=REQ(validator=check_bool, default=False),
) -> HttpResponse:
    subscribed, _ = gather_subscriptions(
        user_profile, include_subscribers=include_subscribers,
    )
    return json_success({"subscriptions": subscribed})

FuncKwargPair = Tuple[Callable[..., HttpResponse], Dict[str, Union[int, Iterable[Any]]]]

add_subscriptions_schema = check_list(
    check_dict_only(
        required_keys=[
            ('name', check_string)
        ],
        optional_keys=[
            ('color', check_color),
            ('description', check_capped_string(Stream.MAX_DESCRIPTION_LENGTH)),
        ],
    ),
)

remove_subscriptions_schema = check_list(check_string)

@has_request_variables
def update_subscriptions_backend(
        request: HttpRequest, user_profile: UserProfile,
        delete: Iterable[str]=REQ(validator=remove_subscriptions_schema, default=[]),
        add: Iterable[Mapping[str, Any]]=REQ(validator=add_subscriptions_schema, default=[]),
) -> HttpResponse:
    if not add and not delete:
        return json_error(_('Nothing to do. Specify at least one of "add" or "delete".'))

    method_kwarg_pairs: List[FuncKwargPair] = [
        (add_subscriptions_backend, dict(streams_raw=add)),
        (remove_subscriptions_backend, dict(streams_raw=delete)),
    ]
    return compose_views(request, user_profile, method_kwarg_pairs)

def compose_views(
    request: HttpRequest,
    user_profile: UserProfile,
    method_kwarg_pairs: "List[FuncKwargPair]",
) -> HttpResponse:
    '''
    This takes a series of view methods from method_kwarg_pairs and calls
    them in sequence, and it smushes all the json results into a single
    response when everything goes right.  (This helps clients avoid extra
    latency hops.)  It rolls back the transaction when things go wrong in
    any one of the composed methods.

    TODO: Move this a utils-like module if we end up using it more widely.
    '''

    json_dict: Dict[str, Any] = {}
    with transaction.atomic():
        for method, kwargs in method_kwarg_pairs:
            response = method(request, user_profile, **kwargs)
            if response.status_code != 200:
                raise JsonableError(response.content)
            json_dict.update(orjson.loads(response.content))
    return json_success(json_dict)

check_principals: Validator[Union[List[str], List[int]]] = check_union(
    [check_list(check_string), check_list(check_int)],
)

@has_request_variables
def remove_subscriptions_backend(
        request: HttpRequest, user_profile: UserProfile,
        streams_raw: Iterable[str]=REQ("subscriptions", validator=remove_subscriptions_schema),
        principals: Optional[Union[List[str], List[int]]]=REQ(validator=check_principals, default=None),
) -> HttpResponse:

    removing_someone_else = check_if_removing_someone_else(user_profile, principals)

    streams_as_dict: List[StreamDict] = []
    for stream_name in streams_raw:
        streams_as_dict.append({"name": stream_name.strip()})

    streams, __ = list_to_streams(streams_as_dict, user_profile,
                                  admin_access_required=removing_someone_else)

    if principals:
        people_to_unsub = {principal_to_user_profile(
            user_profile, principal) for principal in principals}
    else:
        people_to_unsub = {user_profile}

    result: Dict[str, List[str]] = dict(removed=[], not_removed=[])
    (removed, not_subscribed) = bulk_remove_subscriptions(people_to_unsub, streams,
                                                          request.client,
                                                          acting_user=user_profile)

    for (subscriber, removed_stream) in removed:
        result["removed"].append(removed_stream.name)
    for (subscriber, not_subscribed_stream) in not_subscribed:
        result["not_removed"].append(not_subscribed_stream.name)

    return json_success(result)

def you_were_just_subscribed_message(acting_user: UserProfile,
                                     recipient_user: UserProfile,
                                     stream_names: Set[str]) -> str:
    subscriptions = sorted(stream_names)
    if len(subscriptions) == 1:
        with override_language(recipient_user.default_language):
            return _("{user_full_name} subscribed you to the stream {stream_name}.").format(
                user_full_name=f"@**{acting_user.full_name}**",
                stream_name=f"#**{subscriptions[0]}**",
            )

    with override_language(recipient_user.default_language):
        message = _("{user_full_name} subscribed you to the following streams:").format(
            user_full_name=f"@**{acting_user.full_name}**",
        )
    message += "\n\n"
    for stream_name in subscriptions:
        message += f"* #**{stream_name}**\n"
    return message

RETENTION_DEFAULT: Union[str, int] = "realm_default"
EMPTY_PRINCIPALS: Union[Sequence[str], Sequence[int]] = []

@require_non_guest_user
@has_request_variables
def add_subscriptions_backend(
        request: HttpRequest,
        user_profile: UserProfile,
        streams_raw: Iterable[Dict[str, str]]=REQ("subscriptions", validator=add_subscriptions_schema),
        invite_only: bool=REQ(validator=check_bool, default=False),
        stream_post_policy: int=REQ(validator=check_int_in(
            Stream.STREAM_POST_POLICY_TYPES), default=Stream.STREAM_POST_POLICY_EVERYONE),
        history_public_to_subscribers: Optional[bool]=REQ(validator=check_bool, default=None),
        message_retention_days: Union[str, int]=REQ(validator=check_string_or_int,
                                                    default=RETENTION_DEFAULT),
        announce: bool=REQ(validator=check_bool, default=False),
        principals: Union[Sequence[str], Sequence[int]]=REQ(
            validator=check_principals, default=EMPTY_PRINCIPALS,
        ),
        authorization_errors_fatal: bool=REQ(validator=check_bool, default=True),
) -> HttpResponse:
    realm = user_profile.realm
    stream_dicts = []
    color_map = {}
    for stream_dict in streams_raw:
        # 'color' field is optional
        # check for its presence in the streams_raw first
        if 'color' in stream_dict:
            color_map[stream_dict['name']] = stream_dict['color']

        stream_dict_copy: StreamDict = {}
        stream_dict_copy["name"] = stream_dict["name"].strip()

        # We don't allow newline characters in stream descriptions.
        if "description" in stream_dict:
            stream_dict_copy["description"] = stream_dict["description"].replace("\n", " ")

        stream_dict_copy["invite_only"] = invite_only
        stream_dict_copy["stream_post_policy"] = stream_post_policy
        stream_dict_copy["history_public_to_subscribers"] = history_public_to_subscribers
        stream_dict_copy["message_retention_days"] = parse_message_retention_days(
            message_retention_days, Stream.MESSAGE_RETENTION_SPECIAL_VALUES_MAP)

        stream_dicts.append(stream_dict_copy)

    # Validation of the streams arguments, including enforcement of
    # can_create_streams policy and check_stream_name policy is inside
    # list_to_streams.
    existing_streams, created_streams = \
        list_to_streams(stream_dicts, user_profile, autocreate=True)
    authorized_streams, unauthorized_streams = \
        filter_stream_authorization(user_profile, existing_streams)
    if len(unauthorized_streams) > 0 and authorization_errors_fatal:
        return json_error(_("Unable to access stream ({stream_name}).").format(
            stream_name=unauthorized_streams[0].name,
        ))
    # Newly created streams are also authorized for the creator
    streams = authorized_streams + created_streams

    if len(principals) > 0:
        if realm.is_zephyr_mirror_realm and not all(stream.invite_only for stream in streams):
            return json_error(_("You can only invite other Zephyr mirroring users to private streams."))
        if not user_profile.can_subscribe_other_users():
            if user_profile.realm.invite_to_stream_policy == Realm.POLICY_ADMINS_ONLY:
                return json_error(_("Only administrators can modify other users' subscriptions."))
            # Realm.POLICY_MEMBERS_ONLY only fails if the
            # user is a guest, which happens in the decorator above.
            assert user_profile.realm.invite_to_stream_policy == \
                Realm.POLICY_FULL_MEMBERS_ONLY
            return json_error(_("Your account is too new to modify other users' subscriptions."))
        subscribers = {principal_to_user_profile(user_profile, principal) for principal in principals}
    else:
        subscribers = {user_profile}

    (subscribed, already_subscribed) = bulk_add_subscriptions(realm, streams, subscribers,
                                                              acting_user=user_profile, color_map=color_map)

    # We can assume unique emails here for now, but we should eventually
    # convert this function to be more id-centric.
    email_to_user_profile: Dict[str, UserProfile] = {}

    result: Dict[str, Any] = dict(subscribed=defaultdict(list), already_subscribed=defaultdict(list))
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
    return json_success(result)

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

            sender = get_system_bot(settings.NOTIFICATION_BOT)
            recipient_user = email_to_user_profile[email]

            msg = you_were_just_subscribed_message(
                acting_user=user_profile,
                recipient_user=recipient_user,
                stream_names=notify_stream_names,
            )

            notifications.append(
                internal_prep_private_message(
                    realm=user_profile.realm,
                    sender=sender,
                    recipient_user=recipient_user,
                    content=msg))

    if announce and len(created_streams) > 0:
        notifications_stream = user_profile.realm.get_notifications_stream()
        if notifications_stream is not None:
            with override_language(notifications_stream.realm.default_language):
                if len(created_streams) > 1:
                    content = _("{user_name} created the following streams: {stream_str}.")
                else:
                    content = _("{user_name} created a new stream {stream_str}.")
                topic = _('new streams')

            content = content.format(
                user_name=f"@_**{user_profile.full_name}|{user_profile.id}**",
                stream_str=", ".join(f'#**{s.name}**' for s in created_streams)
            )

            sender = get_system_bot(settings.NOTIFICATION_BOT)

            notifications.append(
                internal_prep_stream_message(
                    realm=user_profile.realm,
                    sender=sender,
                    stream=notifications_stream,
                    topic=topic,
                    content=content,
                ),
            )

    if not user_profile.realm.is_zephyr_mirror_realm and len(created_streams) > 0:
        sender = get_system_bot(settings.NOTIFICATION_BOT)
        for stream in created_streams:
            with override_language(stream.realm.default_language):
                notifications.append(
                    internal_prep_stream_message(
                        realm=user_profile.realm,
                        sender=sender,
                        stream=stream,
                        topic=Realm.STREAM_EVENTS_NOTIFICATION_TOPIC,
                        content=_('Stream created by {user_name}.').format(
                            user_name=f"@_**{user_profile.full_name}|{user_profile.id}**",
                        ),
                    ),
                )

    if len(notifications) > 0:
        do_send_messages(notifications, mark_as_read=[user_profile.id])

@has_request_variables
def get_subscribers_backend(request: HttpRequest, user_profile: UserProfile,
                            stream_id: int=REQ('stream', converter=to_non_negative_int)) -> HttpResponse:
    (stream, sub) = access_stream_by_id(
        user_profile,
        stream_id,
        allow_realm_admin=True,
    )
    subscribers = get_subscriber_emails(stream, user_profile)

    return json_success({'subscribers': subscribers})

# By default, lists all streams that the user has access to --
# i.e. public streams plus invite-only streams that the user is on
@has_request_variables
def get_streams_backend(
        request: HttpRequest, user_profile: UserProfile,
        include_public: bool=REQ(validator=check_bool, default=True),
        include_web_public: bool=REQ(validator=check_bool, default=False),
        include_subscribed: bool=REQ(validator=check_bool, default=True),
        include_all_active: bool=REQ(validator=check_bool, default=False),
        include_default: bool=REQ(validator=check_bool, default=False),
        include_owner_subscribed: bool=REQ(validator=check_bool, default=False),
) -> HttpResponse:

    streams = do_get_streams(user_profile, include_public=include_public,
                             include_web_public=include_web_public,
                             include_subscribed=include_subscribed,
                             include_all_active=include_all_active,
                             include_default=include_default,
                             include_owner_subscribed=include_owner_subscribed)
    return json_success({"streams": streams})

@has_request_variables
def get_topics_backend(
        request: HttpRequest, maybe_user_profile: Union[UserProfile, AnonymousUser],
        stream_id: int=REQ(converter=to_non_negative_int,
                           path_only=True)) -> HttpResponse:

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
        result = get_topic_history_for_public_stream(recipient_id=stream.recipient_id)

    else:
        assert user_profile is not None

        (stream, sub) = access_stream_by_id(user_profile, stream_id)

        result = get_topic_history_for_stream(
            user_profile=user_profile,
            recipient_id=stream.recipient_id,
            public_history=stream.is_history_public_to_subscribers(),
        )

    return json_success(dict(topics=result))

@require_realm_admin
@has_request_variables
def delete_in_topic(request: HttpRequest, user_profile: UserProfile,
                    stream_id: int=REQ(converter=to_non_negative_int),
                    topic_name: str=REQ("topic_name")) -> HttpResponse:
    (stream, sub) = access_stream_by_id(user_profile, stream_id)

    messages = messages_for_topic(stream.recipient_id, topic_name)
    if not stream.is_history_public_to_subscribers():
        # Don't allow the user to delete messages that they don't have access to.
        deletable_message_ids = UserMessage.objects.filter(
            user_profile=user_profile, message_id__in=messages).values_list("message_id", flat=True)
        messages = [message for message in messages if message.id in
                    deletable_message_ids]

    do_delete_messages(user_profile.realm, messages)

    return json_success()

@require_post
@authenticated_json_view
@has_request_variables
def json_stream_exists(request: HttpRequest, user_profile: UserProfile, stream_name: str=REQ("stream"),
                       autosubscribe: bool=REQ(validator=check_bool, default=False)) -> HttpResponse:
    check_stream_name(stream_name)

    try:
        (stream, sub) = access_stream_by_name(user_profile, stream_name)
    except JsonableError as e:
        return json_error(e.msg, status=404)

    # access_stream functions return a subscription if and only if we
    # are already subscribed.
    result = {"subscribed": sub is not None}

    # If we got here, we're either subscribed or the stream is public.
    # So if we're not yet subscribed and autosubscribe is enabled, we
    # should join.
    if sub is None and autosubscribe:
        bulk_add_subscriptions(user_profile.realm, [stream], [user_profile], acting_user=user_profile)
        result["subscribed"] = True

    return json_success(result)  # results are ignored for HEAD requests

@has_request_variables
def json_get_stream_id(request: HttpRequest,
                       user_profile: UserProfile,
                       stream_name: str=REQ('stream')) -> HttpResponse:
    (stream, sub) = access_stream_by_name(user_profile, stream_name)
    return json_success({'stream_id': stream.id})

@has_request_variables
def update_subscriptions_property(request: HttpRequest,
                                  user_profile: UserProfile,
                                  stream_id: int=REQ(validator=check_int),
                                  property: str=REQ(),
                                  value: str=REQ()) -> HttpResponse:
    subscription_data = [{"property": property,
                          "stream_id": stream_id,
                          "value": value}]
    return update_subscription_properties_backend(request, user_profile,
                                                  subscription_data=subscription_data)

@has_request_variables
def update_subscription_properties_backend(
        request: HttpRequest, user_profile: UserProfile,
        subscription_data: List[Dict[str, Any]]=REQ(
            validator=check_list(
                check_dict([("stream_id", check_int),
                            ("property", check_string),
                            ("value", check_union([check_string, check_bool]))]),
            ),
        ),
) -> HttpResponse:
    """
    This is the entry point to changing subscription properties. This
    is a bulk endpoint: requestors always provide a subscription_data
    list containing dictionaries for each stream of interest.

    Requests are of the form:

    [{"stream_id": "1", "property": "is_muted", "value": False},
     {"stream_id": "1", "property": "color", "value": "#c2c2c2"}]
    """
    property_converters = {"color": check_color, "in_home_view": check_bool,
                           "is_muted": check_bool,
                           "desktop_notifications": check_bool,
                           "audible_notifications": check_bool,
                           "push_notifications": check_bool,
                           "email_notifications": check_bool,
                           "pin_to_top": check_bool,
                           "wildcard_mentions_notify": check_bool}
    response_data = []

    for change in subscription_data:
        stream_id = change["stream_id"]
        property = change["property"]
        value = change["value"]

        if property not in property_converters:
            return json_error(_("Unknown subscription property: {}").format(property))

        (stream, sub) = access_stream_by_id(user_profile, stream_id)
        if sub is None:
            return json_error(_("Not subscribed to stream id {}").format(stream_id))

        try:
            value = property_converters[property](property, value)
        except ValidationError as error:
            return json_error(error.message)

        do_change_subscription_property(user_profile, sub, stream,
                                        property, value, acting_user=user_profile)

        response_data.append({'stream_id': stream_id,
                              'property': property,
                              'value': value})

    return json_success({"subscription_data": response_data})
