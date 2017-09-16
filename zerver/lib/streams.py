from __future__ import absolute_import

from typing import Any, Iterable, List, Mapping, Set, Text, Tuple

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.lib.actions import check_stream_name, create_streams_if_needed
from zerver.lib.request import JsonableError
from zerver.models import UserProfile, Stream, Subscription, \
    Realm, Recipient, bulk_get_recipients, get_recipient, get_stream, \
    bulk_get_streams

def access_stream_for_delete(user_profile, stream_id):
    # type: (UserProfile, int) -> Stream

    # We should only ever use this for realm admins, who are allowed
    # to delete all streams on their realm, even private streams to
    # which they are not subscribed.  We do an assert here, because
    # all callers should have the require_realm_admin decorator.
    assert(user_profile.is_realm_admin)

    error = _("Invalid stream id")
    try:
        stream = Stream.objects.get(id=stream_id)
    except Stream.DoesNotExist:
        raise JsonableError(error)

    if stream.realm_id != user_profile.realm_id:
        raise JsonableError(error)

    return stream

def access_stream_common(user_profile, stream, error):
    # type: (UserProfile, Stream, Text) -> Tuple[Recipient, Subscription]
    """Common function for backend code where the target use attempts to
    access the target stream, returning all the data fetched along the
    way.  If that user does not have permission to access that stream,
    we throw an exception.  A design goal is that the error message is
    the same for streams you can't access and streams that don't exist."""

    # First, we don't allow any access to streams in other realms.
    if stream.realm_id != user_profile.realm_id:
        raise JsonableError(error)

    recipient = get_recipient(Recipient.STREAM, stream.id)

    try:
        sub = Subscription.objects.get(user_profile=user_profile,
                                       recipient=recipient,
                                       active=True)
    except Subscription.DoesNotExist:
        sub = None

    # If the stream is in your realm and public, you can access it.
    if stream.is_public():
        return (recipient, sub)

    # Or if you are subscribed to the stream, you can access it.
    if sub is not None:
        return (recipient, sub)

    # Otherwise it is a private stream and you're not on it, so throw
    # an error.
    raise JsonableError(error)

def access_stream_by_id(user_profile, stream_id):
    # type: (UserProfile, int) -> Tuple[Stream, Recipient, Subscription]
    error = _("Invalid stream id")
    try:
        stream = Stream.objects.get(id=stream_id)
    except Stream.DoesNotExist:
        raise JsonableError(error)

    (recipient, sub) = access_stream_common(user_profile, stream, error)
    return (stream, recipient, sub)

def check_stream_name_available(realm, name):
    # type: (Realm, Text) -> None
    check_stream_name(name)
    try:
        get_stream(name, realm)
        raise JsonableError(_("Stream name '%s' is already taken") % (name,))
    except Stream.DoesNotExist:
        pass

def access_stream_by_name(user_profile, stream_name):
    # type: (UserProfile, Text) -> Tuple[Stream, Recipient, Subscription]
    error = _("Invalid stream name '%s'" % (stream_name,))
    try:
        stream = get_stream(stream_name, user_profile.realm)
    except Stream.DoesNotExist:
        raise JsonableError(error)

    (recipient, sub) = access_stream_common(user_profile, stream, error)
    return (stream, recipient, sub)

def access_stream_for_unmute_topic(user_profile, stream_name, error):
    # type: (UserProfile, Text, Text) -> Stream
    """
    It may seem a little silly to have this helper function for unmuting
    topics, but it gets around a linter warning, and it helps to be able
    to review all security-related stuff in one place.

    Our policy for accessing streams when you unmute a topic is that you
    don't necessarily need to have an active subscription or even "legal"
    access to the stream.  Instead, we just verify the stream_id has been
    muted in the past (not here, but in the caller).

    Long term, we'll probably have folks just pass us in the id of the
    MutedTopic row to unmute topics.
    """
    try:
        stream = get_stream(stream_name, user_profile.realm)
    except Stream.DoesNotExist:
        raise JsonableError(error)
    return stream

def is_public_stream_by_name(stream_name, realm):
    # type: (Text, Realm) -> bool
    """Determine whether a stream is public, so that
    our caller can decide whether we can get
    historical messages for a narrowing search.

    Because of the way our search is currently structured,
    we may be passed an invalid stream here.  We return
    False in that situation, and subsequent code will do
    validation and raise the appropriate JsonableError.

    Note that this function should only be used in contexts where
    access_stream is being called elsewhere to confirm that the user
    can actually see this stream.
    """
    try:
        stream = get_stream(stream_name, realm)
    except Stream.DoesNotExist:
        return False
    return stream.is_public()

def filter_stream_authorization(user_profile, streams):
    # type: (UserProfile, Iterable[Stream]) -> Tuple[List[Stream], List[Stream]]
    streams_subscribed = set()  # type: Set[int]
    recipients_map = bulk_get_recipients(Recipient.STREAM, [stream.id for stream in streams])
    subs = Subscription.objects.filter(user_profile=user_profile,
                                       recipient__in=list(recipients_map.values()),
                                       active=True)

    for sub in subs:
        streams_subscribed.add(sub.recipient.type_id)

    unauthorized_streams = []  # type: List[Stream]
    for stream in streams:
        # The user is authorized for their own streams
        if stream.id in streams_subscribed:
            continue

        # The user is not authorized for invite_only streams
        if stream.invite_only:
            unauthorized_streams.append(stream)

    authorized_streams = [stream for stream in streams if
                          stream.id not in set(stream.id for stream in unauthorized_streams)]
    return authorized_streams, unauthorized_streams

def list_to_streams(streams_raw, user_profile, autocreate=False):
    # type: (Iterable[Mapping[str, Any]], UserProfile, bool) -> Tuple[List[Stream], List[Stream]]
    """Converts list of dicts to a list of Streams, validating input in the process

    For each stream name, we validate it to ensure it meets our
    requirements for a proper stream name using check_stream_name.

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
        check_stream_name(stream_name)

    existing_streams = []  # type: List[Stream]
    missing_stream_dicts = []  # type: List[Mapping[str, Any]]
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
        created_streams = []  # type: List[Stream]
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
