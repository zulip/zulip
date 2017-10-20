
import datetime
import ujson
import zlib

from django.utils.translation import ugettext as _
from django.utils.timezone import now as timezone_now
from six import binary_type

from zerver.lib.avatar import get_avatar_field
import zerver.lib.bugdown as bugdown
from zerver.lib.cache import cache_with_key, to_dict_cache_key
from zerver.lib.request import JsonableError
from zerver.lib.str_utils import force_bytes, dict_with_str_keys
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.topic_mutes import (
    build_topic_mute_checker,
    topic_is_muted,
)

from zerver.models import (
    get_display_recipient_by_id,
    get_user_profile_by_id,
    query_for_ids,
    Message,
    Realm,
    Recipient,
    Stream,
    Subscription,
    UserProfile,
    UserMessage,
    Reaction
)

from typing import Any, Dict, List, Optional, Set, Tuple, Text, Union
from mypy_extensions import TypedDict

RealmAlertWords = Dict[int, List[Text]]

UnreadMessagesResult = TypedDict('UnreadMessagesResult', {
    'pms': List[Dict[str, Any]],
    'streams': List[Dict[str, Any]],
    'huddles': List[Dict[str, Any]],
    'mentions': List[int],
    'count': int,
})

MAX_UNREAD_MESSAGES = 5000

def sew_messages_and_reactions(messages, reactions):
    # type: (List[Dict[str, Any]], List[Dict[str, Any]]) -> List[Dict[str, Any]]
    """Given a iterable of messages and reactions stitch reactions
    into messages.
    """
    # Add all messages with empty reaction item
    for message in messages:
        message['reactions'] = []

    # Convert list of messages into dictionary to make reaction stitching easy
    converted_messages = {message['id']: message for message in messages}

    for reaction in reactions:
        converted_messages[reaction['message_id']]['reactions'].append(
            reaction)

    return list(converted_messages.values())


def extract_message_dict(message_bytes):
    # type: (binary_type) -> Dict[str, Any]
    return dict_with_str_keys(ujson.loads(zlib.decompress(message_bytes).decode("utf-8")))

def stringify_message_dict(message_dict):
    # type: (Dict[str, Any]) -> binary_type
    return zlib.compress(force_bytes(ujson.dumps(message_dict)))

def message_to_dict(message, apply_markdown):
    # type: (Message, bool) -> Dict[str, Any]
    json = message_to_dict_json(message, apply_markdown)
    obj = extract_message_dict(json)

    '''
    In this codepath we do net yet optimize for clients
    that can compute their own gravatar URLs.
    '''
    client_gravatar = False

    MessageDict.post_process_dicts(
        [obj],
        client_gravatar=client_gravatar,
    )
    return obj

@cache_with_key(to_dict_cache_key, timeout=3600*24)
def message_to_dict_json(message, apply_markdown):
    # type: (Message, bool) -> binary_type
    return MessageDict.to_dict_uncached(message, apply_markdown)

class MessageDict(object):
    @staticmethod
    def post_process_dicts(objs, client_gravatar):
        # type: (List[Dict[str, Any]], bool) -> None
        MessageDict.bulk_hydrate_sender_info(objs)

        for obj in objs:
            MessageDict.hydrate_recipient_info(obj)
            MessageDict.set_sender_avatar(obj, client_gravatar)

            del obj['sender_realm_id']
            del obj['sender_avatar_source']
            del obj['sender_avatar_version']

            del obj['raw_display_recipient']
            del obj['recipient_type']
            del obj['recipient_type_id']
            del obj['sender_is_mirror_dummy']

    @staticmethod
    def to_dict_uncached(message, apply_markdown):
        # type: (Message, bool) -> binary_type
        dct = MessageDict.to_dict_uncached_helper(message, apply_markdown)
        return stringify_message_dict(dct)

    @staticmethod
    def to_dict_uncached_helper(message, apply_markdown):
        # type: (Message, bool) -> Dict[str, Any]
        return MessageDict.build_message_dict(
            apply_markdown = apply_markdown,
            message = message,
            message_id = message.id,
            last_edit_time = message.last_edit_time,
            edit_history = message.edit_history,
            content = message.content,
            subject = message.subject,
            pub_date = message.pub_date,
            rendered_content = message.rendered_content,
            rendered_content_version = message.rendered_content_version,
            sender_id = message.sender.id,
            sender_realm_id = message.sender.realm_id,
            sending_client_name = message.sending_client.name,
            recipient_id = message.recipient.id,
            recipient_type = message.recipient.type,
            recipient_type_id = message.recipient.type_id,
            reactions = Reaction.get_raw_db_rows([message.id])
        )

    @staticmethod
    def get_raw_db_rows(needed_ids):
        # type: (List[int]) -> List[Dict[str, Any]]
        # This is a special purpose function optimized for
        # callers like get_messages_backend().
        fields = [
            'id',
            'subject',
            'pub_date',
            'last_edit_time',
            'edit_history',
            'content',
            'rendered_content',
            'rendered_content_version',
            'recipient_id',
            'recipient__type',
            'recipient__type_id',
            'sender_id',
            'sending_client__name',
            'sender__realm_id',
        ]
        messages = Message.objects.filter(id__in=needed_ids).values(*fields)
        """Adding one-many or Many-Many relationship in values results in N X
        results.

        Link: https://docs.djangoproject.com/en/1.8/ref/models/querysets/#values
        """
        reactions = Reaction.get_raw_db_rows(needed_ids)
        return sew_messages_and_reactions(messages, reactions)

    @staticmethod
    def build_dict_from_raw_db_row(row, apply_markdown):
        # type: (Dict[str, Any], bool) -> Dict[str, Any]
        '''
        row is a row from a .values() call, and it needs to have
        all the relevant fields populated
        '''
        return MessageDict.build_message_dict(
            apply_markdown = apply_markdown,
            message = None,
            message_id = row['id'],
            last_edit_time = row['last_edit_time'],
            edit_history = row['edit_history'],
            content = row['content'],
            subject = row['subject'],
            pub_date = row['pub_date'],
            rendered_content = row['rendered_content'],
            rendered_content_version = row['rendered_content_version'],
            sender_id = row['sender_id'],
            sender_realm_id = row['sender__realm_id'],
            sending_client_name = row['sending_client__name'],
            recipient_id = row['recipient_id'],
            recipient_type = row['recipient__type'],
            recipient_type_id = row['recipient__type_id'],
            reactions=row['reactions']
        )

    @staticmethod
    def build_message_dict(
            apply_markdown,
            message,
            message_id,
            last_edit_time,
            edit_history,
            content,
            subject,
            pub_date,
            rendered_content,
            rendered_content_version,
            sender_id,
            sender_realm_id,
            sending_client_name,
            recipient_id,
            recipient_type,
            recipient_type_id,
            reactions
    ):
        # type: (bool, Optional[Message], int, Optional[datetime.datetime], Optional[Text], Text, Text, datetime.datetime, Optional[Text], Optional[int], int, int, Text, int, int, int, List[Dict[str, Any]]) -> Dict[str, Any]

        obj = dict(
            id                = message_id,
            sender_id         = sender_id,
            recipient_type_id = recipient_type_id,
            recipient_type    = recipient_type,
            recipient_id      = recipient_id,
            subject           = subject,
            timestamp         = datetime_to_timestamp(pub_date),
            client            = sending_client_name)

        obj['sender_realm_id'] = sender_realm_id

        obj['raw_display_recipient'] = get_display_recipient_by_id(
            recipient_id,
            recipient_type,
            recipient_type_id
        )

        obj['subject_links'] = bugdown.subject_links(sender_realm_id, subject)

        if last_edit_time is not None:
            obj['last_edit_timestamp'] = datetime_to_timestamp(last_edit_time)
            assert edit_history is not None
            obj['edit_history'] = ujson.loads(edit_history)

        if apply_markdown:
            if Message.need_to_render_content(rendered_content, rendered_content_version, bugdown.version):
                if message is None:
                    # We really shouldn't be rendering objects in this method, but there is
                    # a scenario where we upgrade the version of bugdown and fail to run
                    # management commands to re-render historical messages, and then we
                    # need to have side effects.  This method is optimized to not need full
                    # blown ORM objects, but the bugdown renderer is unfortunately highly
                    # coupled to Message, and we also need to persist the new rendered content.
                    # If we don't have a message object passed in, we get one here.  The cost
                    # of going to the DB here should be overshadowed by the cost of rendering
                    # and updating the row.
                    # TODO: see #1379 to eliminate bugdown dependencies
                    message = Message.objects.select_related().get(id=message_id)

                assert message is not None  # Hint for mypy.
                # It's unfortunate that we need to have side effects on the message
                # in some cases.
                rendered_content = render_markdown(message, content, realm=message.get_realm())
                message.rendered_content = rendered_content
                message.rendered_content_version = bugdown.version
                message.save_rendered_content()

            if rendered_content is not None:
                obj['content'] = rendered_content
            else:
                obj['content'] = u'<p>[Zulip note: Sorry, we could not understand the formatting of your message]</p>'

            obj['content_type'] = 'text/html'
        else:
            obj['content'] = content
            obj['content_type'] = 'text/x-markdown'

        if rendered_content is not None:
            obj['is_me_message'] = Message.is_status_message(content, rendered_content)
        else:
            obj['is_me_message'] = False

        obj['reactions'] = [ReactionDict.build_dict_from_raw_db_row(reaction)
                            for reaction in reactions]
        return obj

    @staticmethod
    def bulk_hydrate_sender_info(objs):
        # type: (List[Dict[str, Any]]) -> None

        sender_ids = list({
            obj['sender_id']
            for obj in objs
        })

        if not sender_ids:
            return

        query = UserProfile.objects.values(
            'id',
            'full_name',
            'short_name',
            'email',
            'realm__string_id',
            'avatar_source',
            'avatar_version',
            'is_mirror_dummy',
        )

        rows = query_for_ids(query, sender_ids, 'zerver_userprofile.id')

        sender_dict = {
            row['id']: row
            for row in rows
        }

        for obj in objs:
            sender_id = obj['sender_id']
            user_row = sender_dict[sender_id]
            obj['sender_full_name'] = user_row['full_name']
            obj['sender_short_name'] = user_row['short_name']
            obj['sender_email'] = user_row['email']
            obj['sender_realm_str'] = user_row['realm__string_id']
            obj['sender_avatar_source'] = user_row['avatar_source']
            obj['sender_avatar_version'] = user_row['avatar_version']
            obj['sender_is_mirror_dummy'] = user_row['is_mirror_dummy']

    @staticmethod
    def hydrate_recipient_info(obj):
        # type: (Dict[str, Any]) -> None
        '''
        This method hyrdrates recipient info with things
        like full names and emails of senders.  Eventually
        our clients should be able to hyrdrate these fields
        themselves with info they already have on users.
        '''

        display_recipient = obj['raw_display_recipient']
        recipient_type = obj['recipient_type']
        recipient_type_id = obj['recipient_type_id']
        sender_is_mirror_dummy = obj['sender_is_mirror_dummy']
        sender_email = obj['sender_email']
        sender_full_name = obj['sender_full_name']
        sender_short_name = obj['sender_short_name']
        sender_id = obj['sender_id']

        if recipient_type == Recipient.STREAM:
            display_type = "stream"
        elif recipient_type in (Recipient.HUDDLE, Recipient.PERSONAL):
            assert not isinstance(display_recipient, Text)
            display_type = "private"
            if len(display_recipient) == 1:
                # add the sender in if this isn't a message between
                # someone and themself, preserving ordering
                recip = {'email': sender_email,
                         'full_name': sender_full_name,
                         'short_name': sender_short_name,
                         'id': sender_id,
                         'is_mirror_dummy': sender_is_mirror_dummy}
                if recip['email'] < display_recipient[0]['email']:
                    display_recipient = [recip, display_recipient[0]]
                elif recip['email'] > display_recipient[0]['email']:
                    display_recipient = [display_recipient[0], recip]
        else:
            raise AssertionError("Invalid recipient type %s" % (recipient_type,))

        obj['display_recipient'] = display_recipient
        obj['type'] = display_type
        if obj['type'] == 'stream':
            obj['stream_id'] = recipient_type_id

    @staticmethod
    def set_sender_avatar(obj, client_gravatar):
        # type: (Dict[str, Any], bool) -> None
        sender_id = obj['sender_id']
        sender_realm_id = obj['sender_realm_id']
        sender_email = obj['sender_email']
        sender_avatar_source = obj['sender_avatar_source']
        sender_avatar_version = obj['sender_avatar_version']

        obj['avatar_url'] = get_avatar_field(
            user_id=sender_id,
            realm_id=sender_realm_id,
            email=sender_email,
            avatar_source=sender_avatar_source,
            avatar_version=sender_avatar_version,
            medium=False,
            client_gravatar=client_gravatar,
        )

class ReactionDict(object):
    @staticmethod
    def build_dict_from_raw_db_row(row):
        # type: (Dict[str, Any]) -> Dict[str, Any]
        return {'emoji_name': row['emoji_name'],
                'emoji_code': row['emoji_code'],
                'reaction_type': row['reaction_type'],
                'user': {'email': row['user_profile__email'],
                         'id': row['user_profile__id'],
                         'full_name': row['user_profile__full_name']}}


def access_message(user_profile, message_id):
    # type: (UserProfile, int) -> Tuple[Message, UserMessage]
    """You can access a message by ID in our APIs that either:
    (1) You received or have previously accessed via starring
        (aka have a UserMessage row for).
    (2) Was sent to a public stream in your realm.

    We produce consistent, boring error messages to avoid leaking any
    information from a security perspective.
    """
    try:
        message = Message.objects.select_related().get(id=message_id)
    except Message.DoesNotExist:
        raise JsonableError(_("Invalid message(s)"))

    try:
        user_message = UserMessage.objects.select_related().get(user_profile=user_profile,
                                                                message=message)
    except UserMessage.DoesNotExist:
        user_message = None

    if user_message is None:
        if message.recipient.type != Recipient.STREAM:
            # You can't access private messages you didn't receive
            raise JsonableError(_("Invalid message(s)"))
        stream = Stream.objects.get(id=message.recipient.type_id)
        if not stream.is_public():
            # You can't access messages sent to invite-only streams
            # that you didn't receive
            raise JsonableError(_("Invalid message(s)"))
        # So the message is to a public stream
        if stream.realm != user_profile.realm:
            # You can't access public stream messages in other realms
            raise JsonableError(_("Invalid message(s)"))

    # Otherwise, the message must have been sent to a public
    # stream in your realm, so return the message, user_message pair
    return (message, user_message)

def render_markdown(message, content, realm=None, realm_alert_words=None, user_ids=None):
    # type: (Message, Text, Optional[Realm], Optional[RealmAlertWords], Optional[Set[int]]) -> Text
    """Return HTML for given markdown. Bugdown may add properties to the
    message object such as `mentions_user_ids` and `mentions_wildcard`.
    These are only on this Django object and are not saved in the
    database.
    """

    if user_ids is None:
        message_user_ids = set()  # type: Set[int]
    else:
        message_user_ids = user_ids

    if message is not None:
        message.mentions_wildcard = False
        message.mentions_user_ids = set()
        message.alert_words = set()
        message.links_for_preview = set()

        if realm is None:
            realm = message.get_realm()

    possible_words = set()  # type: Set[Text]
    if realm_alert_words is not None:
        for user_id, words in realm_alert_words.items():
            if user_id in message_user_ids:
                possible_words.update(set(words))

    if message is None:
        # If we don't have a message, then we are in the compose preview
        # codepath, so we know we are dealing with a human.
        sent_by_bot = False
    else:
        sent_by_bot = get_user_profile_by_id(message.sender_id).is_bot

    # DO MAIN WORK HERE -- call bugdown to convert
    rendered_content = bugdown.convert(content, message=message, message_realm=realm,
                                       possible_words=possible_words,
                                       sent_by_bot=sent_by_bot)

    if message is not None:
        message.user_ids_with_alert_words = set()

        if realm_alert_words is not None:
            for user_id, words in realm_alert_words.items():
                if user_id in message_user_ids:
                    if set(words).intersection(message.alert_words):
                        message.user_ids_with_alert_words.add(user_id)

    return rendered_content

def huddle_users(recipient_id):
    # type: (int) -> str
    display_recipient = get_display_recipient_by_id(recipient_id,
                                                    Recipient.HUDDLE,
                                                    None)  # type: Union[Text, List[Dict[str, Any]]]

    # Text is for streams.
    assert not isinstance(display_recipient, Text)

    user_ids = [obj['id'] for obj in display_recipient]  # type: List[int]
    user_ids = sorted(user_ids)
    return ','.join(str(uid) for uid in user_ids)

def aggregate_message_dict(input_dict, lookup_fields, collect_senders):
    # type: (Dict[int, Dict[str, Any]], List[str], bool) -> List[Dict[str, Any]]
    lookup_dict = dict()  # type: Dict[Any, Dict]

    '''
    A concrete example might help explain the inputs here:

    input_dict = {
        1002: dict(stream_id=5, topic='foo', sender_id=40),
        1003: dict(stream_id=5, topic='foo', sender_id=41),
        1004: dict(stream_id=6, topic='baz', sender_id=99),
    }

    lookup_fields = ['stream_id', 'topic']

    The first time through the loop:
        attribute_dict = dict(stream_id=5, topic='foo', sender_id=40)
        lookup_dict = (5, 'foo')

    lookup_dict = {
        (5, 'foo'): dict(stream_id=5, topic='foo',
                         unread_message_ids=[1002, 1003],
                         sender_ids=[40, 41],
                        ),
        ...
    }

    result = [
        dict(stream_id=5, topic='foo',
             unread_message_ids=[1002, 1003],
             sender_ids=[40, 41],
            ),
        ...
    ]
    '''

    for message_id, attribute_dict in input_dict.items():
        lookup_key = tuple([attribute_dict[f] for f in lookup_fields])
        if lookup_key not in lookup_dict:
            obj = {}
            for f in lookup_fields:
                obj[f] = attribute_dict[f]
            obj['unread_message_ids'] = []
            if collect_senders:
                obj['sender_ids'] = set()
            lookup_dict[lookup_key] = obj

        bucket = lookup_dict[lookup_key]
        bucket['unread_message_ids'].append(message_id)
        if collect_senders:
            bucket['sender_ids'].add(attribute_dict['sender_id'])

    for dct in lookup_dict.values():
        dct['unread_message_ids'].sort()
        if collect_senders:
            dct['sender_ids'] = sorted(list(dct['sender_ids']))

    sorted_keys = sorted(lookup_dict.keys())

    return [lookup_dict[k] for k in sorted_keys]

def get_inactive_recipient_ids(user_profile):
    # type: (UserProfile) -> List[int]
    rows = Subscription.objects.filter(
        user_profile=user_profile,
        recipient__type=Recipient.STREAM,
        active=False,
    ).values(
        'recipient_id'
    )
    inactive_recipient_ids = [
        row['recipient_id']
        for row in rows]
    return inactive_recipient_ids

def get_muted_stream_ids(user_profile):
    # type: (UserProfile) -> List[int]
    rows = Subscription.objects.filter(
        user_profile=user_profile,
        recipient__type=Recipient.STREAM,
        active=True,
        in_home_view=False,
    ).values(
        'recipient__type_id'
    )
    muted_stream_ids = [
        row['recipient__type_id']
        for row in rows]
    return muted_stream_ids

def get_unread_message_ids_per_recipient(user_profile):
    # type: (UserProfile) -> UnreadMessagesResult
    raw_unread_data = get_raw_unread_data(user_profile)
    aggregated_data = aggregate_unread_data(raw_unread_data)
    return aggregated_data

def get_raw_unread_data(user_profile):
    # type: (UserProfile) -> Dict[str, Any]

    excluded_recipient_ids = get_inactive_recipient_ids(user_profile)

    user_msgs = UserMessage.objects.filter(
        user_profile=user_profile
    ).exclude(
        message__recipient_id__in=excluded_recipient_ids
    ).extra(
        where=[UserMessage.where_unread()]
    ).values(
        'message_id',
        'message__sender_id',
        'message__subject',
        'message__recipient_id',
        'message__recipient__type',
        'message__recipient__type_id',
        'flags',
    ).order_by("-message_id")

    # Limit unread messages for performance reasons.
    user_msgs = list(user_msgs[:MAX_UNREAD_MESSAGES])

    rows = list(reversed(user_msgs))

    muted_stream_ids = get_muted_stream_ids(user_profile)

    topic_mute_checker = build_topic_mute_checker(user_profile)

    def is_row_muted(stream_id, recipient_id, topic):
        # type: (int, int, Text) -> bool
        if stream_id in muted_stream_ids:
            return True

        if topic_mute_checker(recipient_id, topic):
            return True

        return False

    huddle_cache = {}  # type: Dict[int, str]

    def get_huddle_users(recipient_id):
        # type: (int) -> str
        if recipient_id in huddle_cache:
            return huddle_cache[recipient_id]

        user_ids_string = huddle_users(recipient_id)
        huddle_cache[recipient_id] = user_ids_string
        return user_ids_string

    pm_dict = {}
    stream_dict = {}
    unmuted_stream_msgs = set()
    huddle_dict = {}
    mentions = set()

    for row in rows:
        message_id = row['message_id']
        msg_type = row['message__recipient__type']
        recipient_id = row['message__recipient_id']
        sender_id = row['message__sender_id']

        if msg_type == Recipient.STREAM:
            stream_id = row['message__recipient__type_id']
            topic = row['message__subject']
            stream_dict[message_id] = dict(
                stream_id=stream_id,
                topic=topic,
                sender_id=sender_id,
            )
            if not is_row_muted(stream_id, recipient_id, topic):
                unmuted_stream_msgs.add(message_id)

        elif msg_type == Recipient.PERSONAL:
            pm_dict[message_id] = dict(
                sender_id=sender_id,
            )

        elif msg_type == Recipient.HUDDLE:
            user_ids_string = get_huddle_users(recipient_id)
            huddle_dict[message_id] = dict(
                user_ids_string=user_ids_string,
            )

        is_mentioned = (row['flags'] & UserMessage.flags.mentioned) != 0
        if is_mentioned:
            mentions.add(message_id)

    return dict(
        pm_dict=pm_dict,
        stream_dict=stream_dict,
        muted_stream_ids=muted_stream_ids,
        unmuted_stream_msgs=unmuted_stream_msgs,
        huddle_dict=huddle_dict,
        mentions=mentions,
    )

def aggregate_unread_data(raw_data):
    # type: (Dict[str, Any]) -> UnreadMessagesResult

    pm_dict = raw_data['pm_dict']
    stream_dict = raw_data['stream_dict']
    unmuted_stream_msgs = raw_data['unmuted_stream_msgs']
    huddle_dict = raw_data['huddle_dict']
    mentions = list(raw_data['mentions'])

    count = len(pm_dict) + len(unmuted_stream_msgs) + len(huddle_dict)

    pm_objects = aggregate_message_dict(
        input_dict=pm_dict,
        lookup_fields=[
            'sender_id',
        ],
        collect_senders=False,
    )

    stream_objects = aggregate_message_dict(
        input_dict=stream_dict,
        lookup_fields=[
            'stream_id',
            'topic',
        ],
        collect_senders=True,
    )

    huddle_objects = aggregate_message_dict(
        input_dict=huddle_dict,
        lookup_fields=[
            'user_ids_string',
        ],
        collect_senders=False,
    )

    result = dict(
        pms=pm_objects,
        streams=stream_objects,
        huddles=huddle_objects,
        mentions=mentions,
        count=count)  # type: UnreadMessagesResult

    return result

def apply_unread_message_event(user_profile, state, message, flags):
    # type: (UserProfile, Dict[str, Any], Dict[str, Any], List[str]) -> None
    message_id = message['id']
    if message['type'] == 'stream':
        message_type = 'stream'
    elif message['type'] == 'private':
        others = [
            recip for recip in message['display_recipient']
            if recip['id'] != message['sender_id']
        ]
        if len(others) <= 1:
            message_type = 'private'
        else:
            message_type = 'huddle'
    else:
        raise AssertionError("Invalid message type %s" % (message['type'],))

    sender_id = message['sender_id']

    if message_type == 'stream':
        stream_id = message['stream_id']
        topic = message['subject']
        new_row = dict(
            stream_id=stream_id,
            topic=topic,
            sender_id=sender_id,
        )
        state['stream_dict'][message_id] = new_row

        if stream_id not in state['muted_stream_ids']:
            # This next check hits the database.
            if not topic_is_muted(user_profile, stream_id, topic):
                state['unmuted_stream_msgs'].add(message_id)

    elif message_type == 'private':
        sender_id = message['sender_id']
        new_row = dict(
            sender_id=sender_id,
        )
        state['pm_dict'][message_id] = new_row

    else:
        display_recipient = message['display_recipient']
        user_ids = [obj['id'] for obj in display_recipient]
        user_ids = sorted(user_ids)
        user_ids_string = ','.join(str(uid) for uid in user_ids)
        new_row = dict(
            user_ids_string=user_ids_string,
        )
        state['huddle_dict'][message_id] = new_row

    if 'mentioned' in flags:
        state['mentions'].add(message_id)
