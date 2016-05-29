from __future__ import absolute_import
from typing import Any, Optional

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from zerver.lib.request import JsonableError, REQ, has_request_variables
from zerver.decorator import authenticated_json_post_view, \
    authenticated_json_view, \
    get_user_profile_by_email, require_realm_admin
from zerver.lib.actions import bulk_remove_subscriptions, \
    do_change_subscription_property, internal_prep_message, \
    create_stream_if_needed, gather_subscriptions, subscribed_to_stream, \
    bulk_add_subscriptions, do_send_messages, get_subscriber_emails, do_rename_stream, \
    do_deactivate_stream, do_make_stream_public, do_add_default_stream, \
    do_change_stream_description, do_get_streams, do_make_stream_private, \
    do_remove_default_stream
from zerver.lib.response import json_success, json_error, json_response
from zerver.lib.validator import check_string, check_list, check_dict, \
    check_bool, check_variable_type
from zerver.models import UserProfile, Stream, Subscription, \
    Recipient, get_recipient, get_stream, bulk_get_streams, \
    bulk_get_recipients, valid_stream_name, get_active_user_dicts_in_realm

from collections import defaultdict
import ujson
from six.moves import urllib

from zerver.lib.rest import rest_dispatch as _rest_dispatch
import six

rest_dispatch = csrf_exempt((lambda request, *args, **kwargs: _rest_dispatch(request, globals(), *args, **kwargs)))

def list_to_streams(streams_raw, user_profile, autocreate=False, invite_only=False):
    """Converts plaintext stream names to a list of Streams, validating input in the process

    For each stream name, we validate it to ensure it meets our
    requirements for a proper stream name: that is, that it is shorter
    than Stream.MAX_NAME_LENGTH characters and passes
    valid_stream_name.

    This function in autocreate mode should be atomic: either an exception will be raised
    during a precheck, or all the streams specified will have been created if applicable.

    @param streams_raw The list of stream names to process
    @param user_profile The user for whom we are retreiving the streams
    @param autocreate Whether we should create streams if they don't already exist
    @param invite_only Whether newly created streams should have the invite_only bit set
    """
    existing_streams = []
    created_streams = []
    # Validate all streams, getting extant ones, then get-or-creating the rest.
    stream_set = set(stream_name.strip() for stream_name in streams_raw)
    rejects = []
    for stream_name in stream_set:
        if len(stream_name) > Stream.MAX_NAME_LENGTH:
            raise JsonableError("Stream name (%s) too long." % (stream_name,))
        if not valid_stream_name(stream_name):
            raise JsonableError("Invalid stream name (%s)." % (stream_name,))

    existing_stream_map = bulk_get_streams(user_profile.realm, stream_set)

    for stream_name in stream_set:
        stream = existing_stream_map.get(stream_name.lower())
        if stream is None:
            rejects.append(stream_name)
        else:
            existing_streams.append(stream)
    if rejects:
        if not user_profile.can_create_streams():
            raise JsonableError('User cannot create streams.')
        elif not autocreate:
            raise JsonableError("Stream(s) (%s) do not exist" % ", ".join(rejects))

        for stream_name in rejects:
            stream, created = create_stream_if_needed(user_profile.realm,
                                                      stream_name,
                                                      invite_only=invite_only)
            if created:
                created_streams.append(stream)
            else:
                existing_streams.append(stream)

    return existing_streams, created_streams

class PrincipalError(JsonableError):
    def __init__(self, principal, status_code=403):
        self.principal = principal
        self.status_code = status_code

    def to_json_error_msg(self):
        return ("User not authorized to execute queries on behalf of '%s'"
                % (self.principal,))

def principal_to_user_profile(agent, principal):
    principal_doesnt_exist = False
    try:
        principal_user_profile = get_user_profile_by_email(principal)
    except UserProfile.DoesNotExist:
        principal_doesnt_exist = True

    if (principal_doesnt_exist
        or agent.realm != principal_user_profile.realm):
        # We have to make sure we don't leak information about which users
        # are registered for Zulip in a different realm.  We could do
        # something a little more clever and check the domain part of the
        # principal to maybe give a better error message
        raise PrincipalError(principal)

    return principal_user_profile

@require_realm_admin
def deactivate_stream_backend(request, user_profile, stream_name):
    target = get_stream(stream_name, user_profile.realm)
    if not target:
        return json_error('No such stream name')

    if target.invite_only and not subscribed_to_stream(user_profile, target):
        return json_error('Cannot administer invite-only streams this way')

    do_deactivate_stream(target)
    return json_success({})

@require_realm_admin
@has_request_variables
def add_default_stream(request, user_profile, stream_name=REQ):
    do_add_default_stream(user_profile.realm, stream_name)
    return json_success()

@require_realm_admin
@has_request_variables
def remove_default_stream(request, user_profile, stream_name=REQ):
    do_remove_default_stream(user_profile.realm, stream_name)
    return json_success()

@authenticated_json_post_view
@require_realm_admin
@has_request_variables
def json_rename_stream(request, user_profile, old_name=REQ, new_name=REQ):
    do_rename_stream(user_profile.realm, old_name, new_name)
    return json_success()

@authenticated_json_post_view
@require_realm_admin
@has_request_variables
def json_make_stream_public(request, user_profile, stream_name=REQ):
    do_make_stream_public(user_profile, user_profile.realm, stream_name)
    return json_success()

@authenticated_json_post_view
@require_realm_admin
@has_request_variables
def json_make_stream_private(request, user_profile, stream_name=REQ):
    do_make_stream_private(user_profile.realm, stream_name)
    return json_success()

@require_realm_admin
@has_request_variables
def update_stream_backend(request, user_profile, stream_name,
                          description=REQ(validator=check_string, default=None)):
    # type: (HttpRequest, UserProfile, str, Optional[str]) -> HttpResponse
    if description is not None:
       do_change_stream_description(user_profile.realm, stream_name, description)
    return json_success({})

def list_subscriptions_backend(request, user_profile):
    return json_success({"subscriptions": gather_subscriptions(user_profile)[0]})

@transaction.atomic
@has_request_variables
def update_subscriptions_backend(request, user_profile,
                                 delete=REQ(validator=check_list(check_string), default=[]),
                                 add=REQ(validator=check_list(check_dict([['name', check_string]])), default=[])):
    if not add and not delete:
        return json_error('Nothing to do. Specify at least one of "add" or "delete".')

    json_dict = {} # type: Dict[str, Any]
    for method, items in ((add_subscriptions_backend, add), (remove_subscriptions_backend, delete)):
        response = method(request, user_profile, streams_raw=items)
        if response.status_code != 200:
            transaction.rollback()
            return response
        json_dict.update(ujson.loads(response.content))
    return json_success(json_dict)

@authenticated_json_post_view
def json_remove_subscriptions(request, user_profile):
    return remove_subscriptions_backend(request, user_profile)

@has_request_variables
def remove_subscriptions_backend(request, user_profile,
                                 streams_raw = REQ("subscriptions", validator=check_list(check_string)),
                                 principals = REQ(validator=check_list(check_string), default=None)):

    removing_someone_else = principals and \
        set(principals) != set((user_profile.email,))
    if removing_someone_else and not user_profile.is_realm_admin:
        # You can only unsubscribe other people from a stream if you are a realm
        # admin.
        return json_error("This action requires administrative rights")

    streams, _ = list_to_streams(streams_raw, user_profile)

    for stream in streams:
        if removing_someone_else and stream.invite_only and \
                not subscribed_to_stream(user_profile, stream):
            # Even as an admin, you can't remove other people from an
            # invite-only stream you're not on.
            return json_error("Cannot administer invite-only streams this way")

    if principals:
        people_to_unsub = set(principal_to_user_profile(
                user_profile, principal) for principal in principals)
    else:
        people_to_unsub = set([user_profile])

    result = dict(removed=[], not_subscribed=[]) # type: Dict[str, List[str]]
    (removed, not_subscribed) = bulk_remove_subscriptions(people_to_unsub, streams)

    for (subscriber, stream) in removed:
        result["removed"].append(stream.name)
    for (subscriber, stream) in not_subscribed:
        result["not_subscribed"].append(stream.name)

    return json_success(result)

def filter_stream_authorization(user_profile, streams):
    streams_subscribed = set()
    recipients_map = bulk_get_recipients(Recipient.STREAM, [stream.id for stream in streams])
    subs = Subscription.objects.filter(user_profile=user_profile,
                                       recipient__in=list(recipients_map.values()),
                                       active=True)

    for sub in subs:
        streams_subscribed.add(sub.recipient.type_id)

    unauthorized_streams = []
    for stream in streams:
        # The user is authorized for his own streams
        if stream.id in streams_subscribed:
            continue

        # The user is not authorized for invite_only streams
        if stream.invite_only:
            unauthorized_streams.append(stream)

    streams = [stream for stream in streams if
               stream.id not in set(stream.id for stream in unauthorized_streams)]
    return streams, unauthorized_streams

def stream_link(stream_name):
    "Escapes a stream name to make a #narrow/stream/stream_name link"
    return "#narrow/stream/%s" % (urllib.parse.quote(stream_name.encode('utf-8')),)

def stream_button(stream_name):
    stream_name = stream_name.replace('\\', '\\\\')
    stream_name = stream_name.replace(')', '\\)')
    return '!_stream_subscribe_button(%s)' % (stream_name,)

@has_request_variables
def add_subscriptions_backend(request, user_profile,
                              streams_raw = REQ("subscriptions",
                              validator=check_list(check_dict([['name', check_string]]))),
                              invite_only = REQ(validator=check_bool, default=False),
                              announce = REQ(validator=check_bool, default=False),
                              principals = REQ(validator=check_list(check_string), default=None),
                              authorization_errors_fatal = REQ(validator=check_bool, default=True)):
    stream_names = []
    for stream in streams_raw:
        stream_name = stream["name"].strip()
        if len(stream_name) > Stream.MAX_NAME_LENGTH:
            return json_error("Stream name (%s) too long." % (stream_name,))
        if not valid_stream_name(stream_name):
            return json_error("Invalid stream name (%s)." % (stream_name,))
        stream_names.append(stream_name)

    # Enforcement of can_create_streams policy is inside list_to_streams.
    existing_streams, created_streams = \
        list_to_streams(stream_names, user_profile, autocreate=True, invite_only=invite_only)
    authorized_streams, unauthorized_streams = \
        filter_stream_authorization(user_profile, existing_streams)
    if len(unauthorized_streams) > 0 and authorization_errors_fatal:
        return json_error("Unable to access stream (%s)." % unauthorized_streams[0].name)
    # Newly created streams are also authorized for the creator
    streams = authorized_streams + created_streams

    if principals is not None:
        if user_profile.realm.domain == 'mit.edu' and not all(stream.invite_only for stream in streams):
            return json_error("You can only invite other mit.edu users to invite-only streams.")
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
                       "subscribed you to the%s stream [%s](%s)."
                       % (user_profile.full_name,
                          " **invite-only**" if private_streams[subscriptions[0]] else "",
                          subscriptions[0],
                          stream_link(subscriptions[0]),
                        ))
            else:
                msg = ("Hi there!  We thought you'd like to know that %s just "
                       "subscribed you to the following streams: \n\n"
                       % (user_profile.full_name,))
                for stream in subscriptions:
                    msg += "* [%s](%s)%s\n" % (
                        stream,
                        stream_link(stream),
                        " (**invite-only**)" if private_streams[stream] else "")

            if len([s for s in subscriptions if not private_streams[s]]) > 0:
                msg += "\nYou can see historical content on a non-invite-only stream by narrowing to it."
            notifications.append(internal_prep_message(settings.NOTIFICATION_BOT,
                                                       "private", email, "", msg))

    if announce and len(created_streams) > 0:
        notifications_stream = user_profile.realm.notifications_stream
        if notifications_stream is not None:
            if len(created_streams) > 1:
                stream_msg = "the following streams: %s" % \
                              (", ".join('`%s`' % (s.name,) for s in created_streams),)
            else:
                stream_msg = "a new stream `%s`" % (created_streams[0].name)

            stream_buttons = ' '.join(stream_button(s.name) for s in created_streams)
            msg = ("%s just created %s. %s" % (user_profile.full_name,
                                                stream_msg, stream_buttons))
            notifications.append(internal_prep_message(settings.NOTIFICATION_BOT,
                                   "stream",
                                   notifications_stream.name, "Streams", msg,
                                   realm=notifications_stream.realm))
        else:
            msg = ("Hi there!  %s just created a new stream '%s'. %s"
                       % (user_profile.full_name, created_streams[0].name, stream_button(created_streams[0].name)))
            for realm_user_dict in get_active_user_dicts_in_realm(user_profile.realm):
                # Don't announce to yourself or to people you explicitly added
                # (who will get the notification above instead).
                if realm_user_dict['email'] in principals or realm_user_dict['email'] == user_profile.email:
                    continue
                notifications.append(internal_prep_message(settings.NOTIFICATION_BOT,
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
def get_subscribers_backend(request, user_profile, stream_name=REQ('stream')):
    stream = get_stream(stream_name, user_profile.realm)
    if stream is None:
        raise JsonableError("Stream does not exist: %s" % (stream_name,))

    subscribers = get_subscriber_emails(stream, user_profile)

    return json_success({'subscribers': subscribers})

@authenticated_json_post_view
def json_get_subscribers(request, user_profile):
    return get_subscribers_backend(request, user_profile)

# By default, lists all streams that the user has access to --
# i.e. public streams plus invite-only streams that the user is on
@has_request_variables
def get_streams_backend(request, user_profile,
                        include_public=REQ(validator=check_bool, default=True),
                        include_subscribed=REQ(validator=check_bool, default=True),
                        include_all_active=REQ(validator=check_bool, default=False)):

    streams = do_get_streams(user_profile, include_public, include_subscribed,
                             include_all_active)
    return json_success({"streams": streams})

@authenticated_json_post_view
@has_request_variables
def json_stream_exists(request, user_profile, stream=REQ,
                       autosubscribe=REQ(default=False)):
    return stream_exists_backend(request, user_profile, stream, autosubscribe)

def stream_exists_backend(request, user_profile, stream_name, autosubscribe):
    if not valid_stream_name(stream_name):
        return json_error("Invalid characters in stream name")
    stream = get_stream(stream_name, user_profile.realm)
    result = {"exists": bool(stream)}
    if stream is not None:
        recipient = get_recipient(Recipient.STREAM, stream.id)
        if autosubscribe:
            bulk_add_subscriptions([stream], [user_profile])
        result["subscribed"] = Subscription.objects.filter(user_profile=user_profile,
                                                           recipient=recipient,
                                                           active=True).exists()
        return json_success(result) # results are ignored for HEAD requests
    return json_response(data=result, status=404)

def get_subscription_or_die(stream_name, user_profile):
    stream = get_stream(stream_name, user_profile.realm)
    if not stream:
        raise JsonableError("Invalid stream %s" % (stream.name,))
    recipient = get_recipient(Recipient.STREAM, stream.id)
    subscription = Subscription.objects.filter(user_profile=user_profile,
                                               recipient=recipient, active=True)

    if not subscription.exists():
        raise JsonableError("Not subscribed to stream %s" % (stream_name,))

    return subscription

@authenticated_json_view
@has_request_variables
def json_subscription_property(request, user_profile, subscription_data=REQ(
        validator=check_list(
            check_dict([["stream", check_string],
                        ["property", check_string],
                        ["value", check_variable_type(
                            [check_string, check_bool])]])))):
    """
    This is the entry point to changing subscription properties. This
    is a bulk endpoint: requestors always provide a subscription_data
    list containing dictionaries for each stream of interest.

    Requests are of the form:

    [{"stream": "devel", "property": "in_home_view", "value": False},
     {"stream": "devel", "property": "color", "value": "#c2c2c2"}]
    """
    if request.method != "POST":
        return json_error("Invalid verb")

    property_converters = {"color": check_string, "in_home_view": check_bool,
                           "desktop_notifications": check_bool,
                           "audible_notifications": check_bool}
    response_data = []

    for change in subscription_data:
        stream_name = change["stream"]
        property = change["property"]
        value = change["value"]

        if property not in property_converters:
            return json_error("Unknown subscription property: %s" % (property,))

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
