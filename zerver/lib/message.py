from __future__ import absolute_import

import datetime
import ujson
import zlib

from django.utils.translation import ugettext as _
from six import binary_type

from zerver.lib.avatar import avatar_url_from_dict
import zerver.lib.bugdown as bugdown
from zerver.lib.cache import cache_with_key, to_dict_cache_key
from zerver.lib.request import JsonableError
from zerver.lib.str_utils import force_bytes, dict_with_str_keys
from zerver.lib.timestamp import datetime_to_timestamp

from zerver.models import (
    get_display_recipient_by_id,
    get_user_profile_by_id,
    Message,
    Realm,
    Recipient,
    Stream,
    UserProfile,
    UserMessage,
    Reaction
)

from typing import Any, Dict, List, Optional, Set, Tuple, Text

RealmAlertWords = Dict[int, List[Text]]

def extract_message_dict(message_bytes):
    # type: (binary_type) -> Dict[str, Any]
    return dict_with_str_keys(ujson.loads(zlib.decompress(message_bytes).decode("utf-8")))

def stringify_message_dict(message_dict):
    # type: (Dict[str, Any]) -> binary_type
    return zlib.compress(force_bytes(ujson.dumps(message_dict)))

def message_to_dict(message, apply_markdown):
    # type: (Message, bool) -> Dict[str, Any]
    json = message_to_dict_json(message, apply_markdown)
    return extract_message_dict(json)

@cache_with_key(to_dict_cache_key, timeout=3600*24)
def message_to_dict_json(message, apply_markdown):
    # type: (Message, bool) -> binary_type
    return MessageDict.to_dict_uncached(message, apply_markdown)

class MessageDict(object):
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
            sender_email = message.sender.email,
            sender_realm_id = message.sender.realm_id,
            sender_realm_str = message.sender.realm.string_id,
            sender_full_name = message.sender.full_name,
            sender_short_name = message.sender.short_name,
            sender_avatar_source = message.sender.avatar_source,
            sender_avatar_version = message.sender.avatar_version,
            sender_is_mirror_dummy = message.sender.is_mirror_dummy,
            sending_client_name = message.sending_client.name,
            recipient_id = message.recipient.id,
            recipient_type = message.recipient.type,
            recipient_type_id = message.recipient.type_id,
            reactions = Reaction.get_raw_db_rows([message.id])
        )

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
            sender_email = row['sender__email'],
            sender_realm_id = row['sender__realm__id'],
            sender_realm_str = row['sender__realm__string_id'],
            sender_full_name = row['sender__full_name'],
            sender_short_name = row['sender__short_name'],
            sender_avatar_source = row['sender__avatar_source'],
            sender_avatar_version = row['sender__avatar_version'],
            sender_is_mirror_dummy = row['sender__is_mirror_dummy'],
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
            sender_email,
            sender_realm_id,
            sender_realm_str,
            sender_full_name,
            sender_short_name,
            sender_avatar_source,
            sender_avatar_version,
            sender_is_mirror_dummy,
            sending_client_name,
            recipient_id,
            recipient_type,
            recipient_type_id,
            reactions
    ):
        # type: (bool, Optional[Message], int, Optional[datetime.datetime], Optional[Text], Text, Text, datetime.datetime, Optional[Text], Optional[int], int, Text, int, Text, Text, Text, Text, int, bool, Text, int, int, int, List[Dict[str, Any]]) -> Dict[str, Any]

        avatar_url = avatar_url_from_dict(dict(
            avatar_source=sender_avatar_source,
            avatar_version=sender_avatar_version,
            email=sender_email,
            id=sender_id,
            realm_id=sender_realm_id))

        display_recipient = get_display_recipient_by_id(
            recipient_id,
            recipient_type,
            recipient_type_id
        )

        if recipient_type == Recipient.STREAM:
            display_type = "stream"
        elif recipient_type in (Recipient.HUDDLE, Recipient.PERSONAL):
            assert not isinstance(display_recipient, Text)
            display_type = "private"
            if len(display_recipient) == 1:
                # add the sender in if this isn't a message between
                # someone and his self, preserving ordering
                recip = {'email': sender_email,
                         'full_name': sender_full_name,
                         'short_name': sender_short_name,
                         'id': sender_id,
                         'is_mirror_dummy': sender_is_mirror_dummy}
                if recip['email'] < display_recipient[0]['email']:
                    display_recipient = [recip, display_recipient[0]]
                elif recip['email'] > display_recipient[0]['email']:
                    display_recipient = [display_recipient[0], recip]

        obj = dict(
            id                = message_id,
            sender_email      = sender_email,
            sender_full_name  = sender_full_name,
            sender_short_name = sender_short_name,
            sender_realm_str  = sender_realm_str,
            sender_id         = sender_id,
            type              = display_type,
            display_recipient = display_recipient,
            recipient_id      = recipient_id,
            subject           = subject,
            timestamp         = datetime_to_timestamp(pub_date),
            avatar_url        = avatar_url,
            client            = sending_client_name)

        if obj['type'] == 'stream':
            obj['stream_id'] = recipient_type_id

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

        obj['reactions'] = [ReactionDict.build_dict_from_raw_db_row(reaction)
                            for reaction in reactions]
        return obj


class ReactionDict(object):
    @staticmethod
    def build_dict_from_raw_db_row(row):
        # type: (Dict[str, Any]) -> Dict[str, Any]
        return {'emoji_name': row.get('emoji_name'),
                'user': {'email': row.get('user_profile__email'),
                         'id': row.get('user_profile__id'),
                         'full_name': row.get('user_profile__full_name')}}


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

def render_markdown(message, content, realm=None, realm_alert_words=None, message_users=None):
    # type: (Message, Text, Optional[Realm], Optional[RealmAlertWords], Set[UserProfile]) -> Text
    """Return HTML for given markdown. Bugdown may add properties to the
    message object such as `mentions_user_ids` and `mentions_wildcard`.
    These are only on this Django object and are not saved in the
    database.
    """

    if message_users is None:
        message_user_ids = set()  # type: Set[int]
    else:
        message_user_ids = {u.id for u in message_users}

    if message is not None:
        message.mentions_wildcard = False
        message.is_me_message = False
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

        message.is_me_message = Message.is_status_message(content, rendered_content)

    return rendered_content
