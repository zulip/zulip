from __future__ import absolute_import
from typing import Any, Optional, Tuple, List, Set, Iterable, Mapping, Callable, Dict

from django.utils.translation import ugettext as _
from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, HttpResponse

from zerver.lib.request import JsonableError, REQ, has_request_variables
from zerver.decorator import authenticated_json_post_view, \
    authenticated_json_view, \
    get_user_profile_by_email, require_realm_admin, to_non_negative_int
from zerver.lib.actions import bulk_remove_subscriptions, \
    do_change_subscription_property, internal_prep_message, \
    create_streams_if_needed, gather_subscriptions, subscribed_to_stream, \
    bulk_add_subscriptions, do_send_messages, get_subscriber_emails, do_rename_stream, \
    do_deactivate_stream, do_make_stream_public, do_add_default_stream, \
    do_change_stream_description, do_get_streams, do_make_stream_private, \
    do_remove_default_stream, get_topic_history_for_stream
from zerver.lib.response import json_success, json_error, json_response
from zerver.lib.validator import check_string, check_list, check_dict, \
    check_bool, check_variable_type
from zerver.models import UserProfile, Stream, Realm, Subscription, \
    Recipient, get_recipient, get_stream, bulk_get_streams, \
    bulk_get_recipients, valid_stream_name, get_active_user_dicts_in_realm

from collections import defaultdict
import ujson
from six.moves import urllib

import six
from typing import Text

def is_active_subscriber(user_profile, recipient):
    # type: (UserProfile, Recipient) -> bool
    return Subscription.objects.filter(user_profile=user_profile,
                                       recipient=recipient,
                                       active=True).exists()

def list_to_streams(streams_raw, user_profile, autocreate=False):
    # type: (Iterable[Mapping[str, Any]], UserProfile, Optional[bool]) -> Tuple[List[Stream], List[Stream]]
    """Converts list of dicts to a list of Streams, validating input in the process

    For each stream name, we validate it to ensure it meets our
    requirements for a proper stream name: that is, that it is shorter
    than Stream.MAX_NAME_LENGTH characters and passes
    valid_stream_name.

    This function in autocreate mode should be atomic: either an exception will be raised
    during a precheck, or all the streams specified will have been created if applicable.

    @param streams_raw The list of stream dictionaries to process;
      names should already be stripped of whitespace by the caller.
    @param user_profile The user for whom we are retreiving the streams
    @param autocreate Whether we should create streams if they don't already exist
    """
    # Validate all streams, getting extant ones, then get-or-creating the rest.

    stream_set = set(stream_dict["name"] for stream_dict in streams_raw)

    for stream_name in stream_set:
        # Stream names should already have been stripped by the
        # caller, but it makes sense to verify anyway.
        assert stream_name == stream_name.strip()
        if len(stream_name) > Stream.MAX_NAME_LENGTH:
            raise JsonableError(_("Stream name (%s) too long.") % (stream_name,))
        if not valid_stream_name(stream_name):
            raise JsonableError(_("Invalid stream name (%s).") % (stream_name,))

    existing_streams = [] # type: List[Stream]
    missing_stream_dicts = [] # type: List[Mapping[str, Any]]
    existing_stream_map = bulk_get_streams(user_profile.realm, stream_set)

    for stream_dict in streams_raw:
        stream_name = stream_dict["name"]
        stream = existing_stream_map.get(stream_name.lower())
        if stream is None:
            missing_stream_dicts.append(stream_dict)
        else:
            existing_streams.append(stream)

    if len(missing_stream_dicts) == 0:
        # This is the happy path for callers who expected all of these
        # streams to exist already.
        created_streams = [] # type: List[Stream]
    else:
        # autocreate=True path starts here
        if not user_profile.can_create_streams():
            raise JsonableError(_('User cannot create streams.'))
        elif not autocreate:
            raise JsonableError(_("Stream(s) (%s) do not exist") % ", ".join(
                stream_dict["name"] for stream_dict in missing_stream_dicts))

        # We already filtered out existing streams, so dup_streams
        # will normally be an empty list below, but we protect against somebody
        # else racing to create the same stream.  (This is not an entirely
        # paranoid approach, since often on Zulip two people will discuss
        # creating a new stream, and both people eagerly do it.)
        created_streams, dup_streams = create_streams_if_needed(realm=user_profile.realm,
                                                                stream_dicts=missing_stream_dicts)
        existing_streams += dup_streams

    return existing_streams, created_streams

class PrincipalError(JsonableError):
    def __init__(self, principal, status_code=403):
        # type: (Text, int) -> None
        self.principal = principal # type: Text
        self.status_code = status_code # type: int

    def to_json_error_msg(self):
        # type: () -> Text
        return ("User not authorized to execute queries on behalf of '%s'"
                % (self.principal,))

def principal_to_user_profile(agent, principal):
    # type: (UserProfile, Text) -> UserProfile
    principal_doesnt_exist = False
    try:
        principal_user_profile = get_user_profile_by_email(principal)
    except UserProfile.DoesNotExist:
        principal_doesnt_exist = True

    if (principal_doesnt_exist or
            agent.realm != principal_user_profile.realm):
        # We have to make sure we don't leak information about which users
        # are registered for Zulip in a different realm.  We could do
        # something a little more clever and check the domain part of the
        # principal to maybe give a better error message
        raise PrincipalError(principal)

    return principal_user_profile

@require_realm_admin
def deactivate_stream_backend(request, user_profile, stream_id):
    # type: (HttpRequest, UserProfile, int) -> HttpResponse
    target = get_and_validate_stream_by_id(stream_id, user_profile.realm)

    if target.invite_only and not subscribed_to_stream(user_profile, target):
        return json_error(_('Cannot administer invite-only streams this way'))

    do_deactivate_stream(target)
    return json_success()

@require_realm_admin
@has_request_variables
def add_default_stream(request, user_profile, stream_name=REQ()):
    # type: (HttpRequest, UserProfile, Text) -> HttpResponse
    do_add_default_stream(user_profile.realm, stream_name)
    return json_success()

@require_realm_admin
@has_request_variables
def remove_default_stream(request, user_profile, stream_name=REQ()):
    # type: (HttpRequest, UserProfile, Text) -> HttpResponse
    do_remove_default_stream(user_profile.realm, stream_name)
    return json_success()

@require_realm_admin
@has_request_variables
def update_stream_backend(request, user_profile, stream_id,
                          description=REQ(validator=check_string, default=None),
                          is_private=REQ(validator=check_bool, default=None),
                          new_name=REQ(validator=check_string, default=None)):
    # type: (HttpRequest, UserProfile, int, Optional[Text], Optional[bool], Optional[Text]) -> HttpResponse
    stream = get_and_validate_stream_by_id(stream_id, user_profile.realm)
    stream_name = stream.name

    if description is not None:
        do_change_stream_description(user_profile.realm, stream_name, description)
    if stream_name is not None and new_name is not None:
        do_rename_stream(user_profile.realm, stream_name, new_name)
    if is_private is not None:
        if is_private:
            do_make_stream_private(user_profile.realm, stream_name)
        else:
            do_make_stream_public(user_profile, user_profile.realm, stream_name)
    return json_success()

def list_subscriptions_backend(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    return json_success({"subscriptions": gather_subscriptions(user_profile)[0]})

FuncKwargPair = Tuple[Callable[..., HttpResponse], Dict[str, Iterable[Any]]]

@has_request_variables
def update_subscriptions_backend(request, user_profile,
                                 delete=REQ(validator=check_list(check_string), default=[]),
                                 add=REQ(validator=check_list(check_dict([('name', check_string)])), default=[])):
    # type: (HttpRequest, UserProfile, Iterable[Text], Iterable[Mapping[str, Any]]) -> HttpResponse
    if not add and not delete:
        return json_error(_('Nothing to do. Specify at least one of "add" or "delete".'))

    method_kwarg_pairs = [
        (add_subscriptions_backend, dict(streams_raw=add)),
        (remove_subscriptions_backend, dict(streams_raw=delete))
    ] # type: List[FuncKwargPair]
    return compose_views(request, user_profile, method_kwarg_pairs)

def compose_views(request, user_profile, method_kwarg_pairs):
    # type: (HttpRequest, UserProfile, List[FuncKwargPair]) -> HttpResponse
    '''
    This takes a series of view methods from method_kwarg_pairs and calls
    them in sequence, and it smushes all the json results into a single
    response when everything goes right.  (This helps clients avoid extra
    latency hops.)  It rolls back the transaction when things go wrong in
    any one of the composed methods.

    TODO: Move this a utils-like module if we end up using it more widely.
    '''

    json_dict = {} # type: Dict[str, Any]
    with transaction.atomic():
        for method, kwargs in method_kwarg_pairs:
            response = method(request, user_profile, **kwargs)
            if response.status_code != 200:
                raise JsonableError(response.content)
            json_dict.update(ujson.loads(response.content))
    return json_success(json_dict)

@authenticated_json_post_view
def json_remove_subscriptions(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    return remove_subscriptions_backend(request, user_profile)

@has_request_variables
def remove_subscriptions_backend(request, user_profile,
                                 streams_raw = REQ("subscriptions", validator=check_list(check_string)),
                                 principals = REQ(validator=check_list(check_string), default=None)):
    # type: (HttpRequest, UserProfile, Iterable[Text], Optional[Iterable[Text]]) -> HttpResponse

    removing_someone_else = principals and \
        set(principals) != set((user_profile.email,))
    if removing_someone_else and not user_profile.is_realm_admin:
        # You can only unsubscribe other people from a stream if you are a realm
        # admin.
        return json_error(_("This action requires administrative rights"))

    streams_as_dict = []
    for stream_name in streams_raw:
        streams_as_dict.append({"name": stream_name.strip()})

    streams, __ = list_to_streams(streams_as_dict, user_profile)

    for stream in streams:
        if removing_someone_else and stream.invite_only and \
                not subscribed_to_stream(user_profile, stream):
            # Even as an admin, you can't remove other people from an
            # invite-only stream you're not on.
            return json_error(_("Cannot administer invite-only streams this way"))

    if principals:
        people_to_unsub = set(principal_to_user_profile(
            user_profile, principal) for principal in principals)
    else:
        people_to_unsub = set([user_profile])

    result = dict(removed=[], not_subscribed=[]) # type: Dict[str, List[Text]]
    (removed, not_subscribed) = bulk_remove_subscriptions(people_to_unsub, streams)

    for (subscriber, stream) in removed:
        result["removed"].append(stream.name)
    for (subscriber, stream) in not_subscribed:
        result["not_subscribed"].append(stream.name)

    return json_success(result)

def filter_stream_authorization(user_profile, streams):
    # type: (UserProfile, Iterable[Stream]) -> Tuple[List[Stream], List[Stream]]
    streams_subscribed = set() # type: Set[int]
    recipients_map = bulk_get_recipients(Recipient.STREAM, [stream.id for stream in streams])
    subs = Subscription.objects.filter(user_profile=user_profile,
                                       recipient__in=list(recipients_map.values()),
                                       active=True)

    for sub in subs:
        streams_subscribed.add(sub.recipient.type_id)

    unauthorized_streams = [] # type: List[Stream]
    for stream in streams:
        # The user is authorized for his own streams
        if stream.id in streams_subscribed:
            continue

        # The user is not authorized for invite_only streams
        if stream.invite_only:
            unauthorized_streams.append(stream)

    authorized_streams = [stream for stream in streams if
                          stream.id not in set(stream.id for stream in unauthorized_streams)]
    return authorized_streams, unauthorized_streams

@has_request_variables
def add_subscriptions_backend(request, user_profile,
                              streams_raw = REQ("subscriptions",
                                                validator=check_list(check_dict([('name', check_string)]))),
                              invite_only = REQ(validator=check_bool, default=False),
                              announce = REQ(validator=check_bool, default=False),
                              principals = REQ(validator=check_list(check_string), default=None),
                              authorization_errors_fatal = REQ(validator=check_bool, default=True)):
    # type: (HttpRequest, UserProfile, Iterable[Mapping[str, Text]], bool, bool, Optional[List[Text]], bool) -> HttpResponse
    stream_dicts = []
    for stream_dict in streams_raw:
        stream_dict_copy = {} # type: Dict[str, Any]
        for field in stream_dict:
            stream_dict_copy[field] = stream_dict[field]
        # Strip the stream name here.
        stream_dict_copy['name'] = stream_dict_copy['name'].strip()
        stream_dict_copy["invite_only"] = invite_only
        stream_dicts.append(stream_dict_copy)

    # Validation of the streams arguments, including enforcement of
    # can_create_streams policy and valid_stream_name policy is inside
    # list_to_streams.
    existing_streams, created_streams = \
        list_to_streams(stream_dicts, user_profile, autocreate=True)
    authorized_streams, unauthorized_streams = \
        filter_stream_authorization(user_profile, existing_streams)
    if len(unauthorized_streams) > 0 and authorization_errors_fatal:
        return json_error(_("Unable to access stream (%s).") % unauthorized_streams[0].name)
    # Newly created streams are also authorized for the creator
    streams = authorized_streams + created_streams

    if principals is not None:
        if user_profile.realm.is_zephyr_mirror_realm and not all(stream.invite_only for stream in streams):
            return json_error(_("You can only invite other Zephyr mirroring users to invite-only streams."))
        subscribers = set(principal_to_user_profile(user_profile, principal) for principal in principals)
    else:
        subscribers = set([user_profile])

    (subscribed, already_subscribed) = bulk_add_subscriptions(streams, subscribers)

    result = dict(subscribed=defaultdict(list), already_subscribed=defaultdict(list)) # type: Dict[str, Any]
    for (subscriber, stream) in subscribed:
        result["subscribed"][subscriber.email].append(stream.name)
    for (subscriber, stream) in already_subscribed:
        result["already_subscribed"][subscriber.email].append(stream.name)

    private_streams = dict((stream.name, stream.invite_only) for stream in streams)
    bots = dict((subscriber.email, subscriber.is_bot) for subscriber in subscribers)

    # Inform the user if someone else subscribed them to stuff,
    # or if a new stream was created with the "announce" option.
    notifications = []
    if principals and result["subscribed"]:
        for email, subscriptions in six.iteritems(result["subscribed"]):
            if email == user_profile.email:
                # Don't send a Zulip if you invited yourself.
                continue
            if bots[email]:
                # Don't send invitation Zulips to bots
                continue

            if len(subscriptions) == 1:
                msg = ("Hi there!  We thought you'd like to know that %s just "
                       "subscribed you to the%s stream #**%s**."
                       % (user_profile.full_name,
                          " **invite-only**" if private_streams[subscriptions[0]] else "",
                          subscriptions[0],
                          ))
            else:
                msg = ("Hi there!  We thought you'd like to know that %s just "
                       "subscribed you to the following streams: \n\n"
                       % (user_profile.full_name,))
                for stream in subscriptions:
                    msg += "* #**%s**%s\n" % (
                        stream,
                        " (**invite-only**)" if private_streams[stream] else "")

            if len([s for s in subscriptions if not private_streams[s]]) > 0:
                msg += "\nYou can see historical content on a non-invite-only stream by narrowing to it."
            notifications.append(internal_prep_message(
                user_profile.realm, settings.NOTIFICATION_BOT,
                "private", email, "", msg))

    if announce and len(created_streams) > 0:
        notifications_stream = user_profile.realm.notifications_stream
        if notifications_stream is not None:
            if len(created_streams) > 1:
                stream_msg = "the following streams: %s" % (", ".join('#**%s**' % s.name for s in created_streams))
            else:
                stream_msg = "a new stream #**%s**." % created_streams[0].name
            msg = ("%s just created %s" % (user_profile.full_name, stream_msg))
            notifications.append(
                internal_prep_message(user_profile.realm, settings.NOTIFICATION_BOT,
                                      "stream",
                                      notifications_stream.name, "Streams", msg))
        else:
            msg = ("Hi there!  %s just created a new stream #**%s**."
                   % (user_profile.full_name, created_streams[0].name))
            for realm_user_dict in get_active_user_dicts_in_realm(user_profile.realm):
                # Don't announce to yourself or to people you explicitly added
                # (who will get the notification above instead).
                if realm_user_dict['email'] in principals or realm_user_dict['email'] == user_profile.email:
                    continue
                notifications.append(internal_prep_message(
                    user_profile.realm, settings.NOTIFICATION_BOT,
                    "private",
                    realm_user_dict['email'], "", msg))

    if len(notifications) > 0:
        do_send_messages(notifications)

    result["subscribed"] = dict(result["subscribed"])
    result["already_subscribed"] = dict(result["already_subscribed"])
    if not authorization_errors_fatal:
        result["unauthorized"] = [stream.name for stream in unauthorized_streams]
    return json_success(result)

@has_request_variables
def get_subscribers_backend(request, user_profile,
                            stream_id=REQ('stream', converter=to_non_negative_int)):
    # type: (HttpRequest, UserProfile, int) -> HttpResponse
    stream = get_and_validate_stream_by_id(stream_id, user_profile.realm)
    subscribers = get_subscriber_emails(stream, user_profile)

    return json_success({'subscribers': subscribers})

# By default, lists all streams that the user has access to --
# i.e. public streams plus invite-only streams that the user is on
@has_request_variables
def get_streams_backend(request, user_profile,
                        include_public=REQ(validator=check_bool, default=True),
                        include_subscribed=REQ(validator=check_bool, default=True),
                        include_all_active=REQ(validator=check_bool, default=False),
                        include_default=REQ(validator=check_bool, default=False)):
    # type: (HttpRequest, UserProfile, bool, bool, bool, bool) -> HttpResponse

    streams = do_get_streams(user_profile, include_public=include_public,
                             include_subscribed=include_subscribed,
                             include_all_active=include_all_active,
                             include_default=include_default)
    return json_success({"streams": streams})

@has_request_variables
def get_topics_backend(request, user_profile,
                       stream_id=REQ(converter=to_non_negative_int)):
    # type: (HttpRequest, UserProfile, int) -> HttpResponse
    stream = get_and_validate_stream_by_id(stream_id, user_profile.realm)

    if stream.realm_id != user_profile.realm_id:
        return json_error(_("Invalid stream id"))

    recipient = get_recipient(Recipient.STREAM, stream.id)

    if not stream.is_public():
        if not is_active_subscriber(user_profile=user_profile,
                                    recipient=recipient):
            return json_error(_("Invalid stream id"))

    result = get_topic_history_for_stream(
        user_profile=user_profile,
        recipient=recipient,
    )

    # Our data structure here is a list of tuples of
    # (topic name, unread count), and it's reverse chronological,
    # so the most recent topic is the first element of the list.
    return json_success(dict(topics=result))


@authenticated_json_post_view
@has_request_variables
def json_stream_exists(request, user_profile, stream=REQ(),
                       autosubscribe=REQ(default=False)):
    # type: (HttpRequest, UserProfile, Text, bool) -> HttpResponse
    if not valid_stream_name(stream):
        return json_error(_("Invalid characters in stream name"))
    try:
        stream_id = Stream.objects.get(realm=user_profile.realm, name=stream).id
    except Stream.DoesNotExist:
        stream_id = None
    return stream_exists_backend(request, user_profile, stream_id, autosubscribe)

def stream_exists_backend(request, user_profile, stream_id, autosubscribe):
    # type: (HttpRequest, UserProfile, int, bool) -> HttpResponse
    try:
        stream = get_and_validate_stream_by_id(stream_id, user_profile.realm)
    except JsonableError:
        stream = None
    result = {"exists": bool(stream)}
    if stream is not None:
        recipient = get_recipient(Recipient.STREAM, stream.id)
        if not stream.invite_only and autosubscribe:
            bulk_add_subscriptions([stream], [user_profile])
        result["subscribed"] = is_active_subscriber(
            user_profile=user_profile,
            recipient=recipient)

        return json_success(result) # results are ignored for HEAD requests
    return json_response(data=result, status=404)

def get_and_validate_stream_by_id(stream_id, realm):
    # type: (int, Realm) -> Stream
    try:
        stream = Stream.objects.get(pk=stream_id, realm_id=realm.id)
    except Stream.DoesNotExist:
        raise JsonableError(_("Invalid stream id"))
    return stream

@has_request_variables
def json_get_stream_id(request, user_profile, stream=REQ()):
    # type: (HttpRequest, UserProfile, Text) -> HttpResponse
    try:
        stream_id = Stream.objects.get(realm=user_profile.realm, name=stream).id
    except Stream.DoesNotExist:
        return json_error(_("No such stream name"))
    return json_success({'stream_id': stream_id})

def get_subscription_or_die(stream_name, user_profile):
    # type: (Text, UserProfile) -> Subscription
    stream = get_stream(stream_name, user_profile.realm)
    if not stream:
        raise JsonableError(_("Invalid stream %s") % (stream_name,))
    recipient = get_recipient(Recipient.STREAM, stream.id)
    subscription = Subscription.objects.filter(user_profile=user_profile,
                                               recipient=recipient, active=True)

    if not subscription.exists():
        raise JsonableError(_("Not subscribed to stream %s") % (stream_name,))

    return subscription

@authenticated_json_view
@has_request_variables
def json_subscription_property(request, user_profile, subscription_data=REQ(
        validator=check_list(
            check_dict([("stream", check_string),
                        ("property", check_string),
                        ("value", check_variable_type(
                            [check_string, check_bool]))])))):
    # type: (HttpRequest, UserProfile, List[Dict[str, Any]]) -> HttpResponse
    """
    This is the entry point to changing subscription properties. This
    is a bulk endpoint: requestors always provide a subscription_data
    list containing dictionaries for each stream of interest.

    Requests are of the form:

    [{"stream": "devel", "property": "in_home_view", "value": False},
     {"stream": "devel", "property": "color", "value": "#c2c2c2"}]
    """
    if request.method != "POST":
        return json_error(_("Invalid verb"))

    property_converters = {"color": check_string, "in_home_view": check_bool,
                           "desktop_notifications": check_bool,
                           "audible_notifications": check_bool,
                           "pin_to_top": check_bool}
    response_data = []

    for change in subscription_data:
        stream_name = change["stream"]
        property = change["property"]
        value = change["value"]

        if property not in property_converters:
            return json_error(_("Unknown subscription property: %s") % (property,))

        sub = get_subscription_or_die(stream_name, user_profile)[0]

        property_conversion = property_converters[property](property, value)
        if property_conversion:
            return json_error(property_conversion)

        do_change_subscription_property(user_profile, sub, stream_name,
                                        property, value)

        response_data.append({'stream': stream_name,
                              'property': property,
                              'value': value})

    return json_success({"subscription_data": response_data})
