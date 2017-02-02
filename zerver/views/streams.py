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
    gather_subscriptions, subscribed_to_stream, \
    bulk_add_subscriptions, do_send_messages, get_subscriber_emails, do_rename_stream, \
    do_deactivate_stream, do_change_stream_invite_only, do_add_default_stream, \
    do_change_stream_description, do_get_streams, \
    do_remove_default_stream, get_topic_history_for_stream
from zerver.lib.response import json_success, json_error, json_response
from zerver.lib.streams import access_stream_by_id, access_stream_by_name, \
    check_stream_name, check_stream_name_available, filter_stream_authorization, \
    list_to_streams
from zerver.lib.validator import check_string, check_list, check_dict, \
    check_bool, check_variable_type
from zerver.models import UserProfile, Stream, Realm, Subscription, \
    Recipient, get_recipient, get_stream, get_active_user_dicts_in_realm

from collections import defaultdict
import ujson
from six.moves import urllib

import six
from typing import Text

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
    (stream, recipient, sub) = access_stream_by_id(user_profile, stream_id)
    do_deactivate_stream(stream)
    return json_success()

@require_realm_admin
@has_request_variables
def add_default_stream(request, user_profile, stream_name=REQ()):
    # type: (HttpRequest, UserProfile, Text) -> HttpResponse
    (stream, recipient, sub) = access_stream_by_name(user_profile, stream_name)
    do_add_default_stream(stream)
    return json_success()

@require_realm_admin
@has_request_variables
def remove_default_stream(request, user_profile, stream_name=REQ()):
    # type: (HttpRequest, UserProfile, Text) -> HttpResponse
    (stream, recipient, sub) = access_stream_by_name(user_profile, stream_name)
    do_remove_default_stream(stream)
    return json_success()

@require_realm_admin
@has_request_variables
def update_stream_backend(request, user_profile, stream_id,
                          description=REQ(validator=check_string, default=None),
                          is_private=REQ(validator=check_bool, default=None),
                          new_name=REQ(validator=check_string, default=None)):
    # type: (HttpRequest, UserProfile, int, Optional[Text], Optional[bool], Optional[Text]) -> HttpResponse
    (stream, recipient, sub) = access_stream_by_id(user_profile, stream_id)

    if description is not None:
        do_change_stream_description(stream, description)
    if new_name is not None:
        new_name = new_name.strip()
        if stream.name == new_name:
            return json_error(_("Stream already has that name!"))
        if stream.name.lower() != new_name.lower():
            # Check that the stream name is available (unless we are
            # are only changing the casing of the stream name).
            check_stream_name_available(user_profile.realm, new_name)
        do_rename_stream(stream, new_name)
    if is_private is not None:
        do_change_stream_invite_only(stream, is_private)
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

@has_request_variables
def add_subscriptions_backend(request, user_profile,
                              streams_raw = REQ("subscriptions",
                                                validator=check_list(check_dict([('name', check_string)]))),
                              invite_only = REQ(validator=check_bool, default=False),
                              announce = REQ(validator=check_bool, default=False),
                              principals = REQ(validator=check_list(check_string), default=[]),
                              authorization_errors_fatal = REQ(validator=check_bool, default=True)):
    # type: (HttpRequest, UserProfile, Iterable[Mapping[str, Text]], bool, bool, List[Text], bool) -> HttpResponse
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
    # can_create_streams policy and check_stream_name policy is inside
    # list_to_streams.
    existing_streams, created_streams = \
        list_to_streams(stream_dicts, user_profile, autocreate=True)
    authorized_streams, unauthorized_streams = \
        filter_stream_authorization(user_profile, existing_streams)
    if len(unauthorized_streams) > 0 and authorization_errors_fatal:
        return json_error(_("Unable to access stream (%s).") % unauthorized_streams[0].name)
    # Newly created streams are also authorized for the creator
    streams = authorized_streams + created_streams

    if len(principals) > 0:
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
    if len(principals) > 0 and result["subscribed"]:
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
        notifications_stream = user_profile.realm.notifications_stream  # type: Optional[Stream]
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
    (stream, recipient, sub) = access_stream_by_id(user_profile, stream_id)
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
    (stream, recipient, sub) = access_stream_by_id(user_profile, stream_id)

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
def json_stream_exists(request, user_profile, stream_name=REQ("stream"),
                       autosubscribe=REQ(validator=check_bool, default=False)):
    # type: (HttpRequest, UserProfile, Text, bool) -> HttpResponse
    check_stream_name(stream_name)

    try:
        (stream, recipient, sub) = access_stream_by_name(user_profile, stream_name)
    except JsonableError as e:
        result = {"exists": False}
        return json_error(e.error, data=result, status=404)

    # access_stream functions return a subscription if and only if we
    # are already subscribed.
    result = {"exists": True,
              "subscribed": sub is not None}

    # If we got here, we're either subscribed or the stream is public.
    # So if we're not yet subscribed and autosubscribe is enabled, we
    # should join.
    if sub is None and autosubscribe:
        bulk_add_subscriptions([stream], [user_profile])
        result["subscribed"] = True

    return json_success(result) # results are ignored for HEAD requests

@has_request_variables
def json_get_stream_id(request, user_profile, stream_name=REQ('stream')):
    # type: (HttpRequest, UserProfile, Text) -> HttpResponse
    (stream, recipient, sub) = access_stream_by_name(user_profile, stream_name)
    return json_success({'stream_id': stream.id})

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

        (stream, recipient, sub) = access_stream_by_name(user_profile, stream_name)
        if sub is None:
            return json_error(_("Not subscribed to stream %s") % (stream_name,))

        property_conversion = property_converters[property](property, value)
        if property_conversion:
            return json_error(property_conversion)

        do_change_subscription_property(user_profile, sub, stream_name,
                                        property, value)

        response_data.append({'stream': stream_name,
                              'property': property,
                              'value': value})

    return json_success({"subscription_data": response_data})
