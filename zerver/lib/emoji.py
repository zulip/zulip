from __future__ import absolute_import

import os
import re
import ujson

from django.utils.translation import ugettext as _
from typing import Optional, Text, Tuple

from zerver.lib.request import JsonableError
from zerver.lib.upload import upload_backend
from zerver.models import Reaction, Realm, RealmEmoji, UserProfile

# Until migration to iamcal dataset is complete use the unified
# reactions file to convert a reaction emoji name to codepoint.
# Once the migration is complete this will be switched to use
# name_to_codepoint map.
ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
UNIFIED_REACTIONS_FILE_PATH = os.path.join(ZULIP_PATH, 'zerver', 'management', 'data', 'unified_reactions.json')
with open(UNIFIED_REACTIONS_FILE_PATH) as fp:
    unified_reactions = ujson.load(fp)

def emoji_name_to_emoji_code(realm, emoji_name):
    # type: (Realm, Text) -> Tuple[Text, Text]
    realm_emojis = realm.get_emoji()
    if emoji_name in realm_emojis and not realm_emojis[emoji_name]['deactivated']:
        return emoji_name, Reaction.REALM_EMOJI
    if emoji_name == 'zulip':
        return emoji_name, Reaction.ZULIP_EXTRA_EMOJI
    if emoji_name in unified_reactions:
        return unified_reactions[emoji_name], Reaction.UNICODE_EMOJI
    raise JsonableError(_("Emoji '%s' does not exist" % (emoji_name,)))

def check_valid_emoji(realm, emoji_name):
    # type: (Realm, Text) -> None
    emoji_name_to_emoji_code(realm, emoji_name)

def check_emoji_admin(user_profile, emoji_name=None):
    # type: (UserProfile, Optional[Text]) -> None
    """Raises an exception if the user cannot administer the target realm
    emoji name in their organization."""

    # Realm administrators can always administer emoji
    if user_profile.is_realm_admin:
        return
    if user_profile.realm.add_emoji_by_admins_only:
        raise JsonableError(_("Must be a realm administrator"))

    # Otherwise, normal users can add emoji
    if emoji_name is None:
        return

    # Additionally, normal users can remove emoji they themselves added
    emoji = RealmEmoji.objects.filter(name=emoji_name).first()
    current_user_is_author = (emoji is not None and
                              emoji.author is not None and
                              emoji.author.id == user_profile.id)
    if not user_profile.is_realm_admin and not current_user_is_author:
        raise JsonableError(_("Must be a realm administrator or emoji author"))

def check_valid_emoji_name(emoji_name):
    # type: (Text) -> None
    if re.match('^[0-9a-z.\-_]+(?<![.\-_])$', emoji_name):
        return
    raise JsonableError(_("Invalid characters in emoji name"))

def get_emoji_url(emoji_file_name, realm_id):
    # type: (Text, int) -> Text
    return upload_backend.get_emoji_url(emoji_file_name, realm_id)


def get_emoji_file_name(emoji_file_name, emoji_name):
    # type: (Text, Text) -> Text
    _, image_ext = os.path.splitext(emoji_file_name)
    return ''.join((emoji_name, image_ext))
