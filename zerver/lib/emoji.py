from __future__ import absolute_import

import re

from django.utils.translation import ugettext as _
from typing import Text

from zerver.lib.bugdown import name_to_codepoint
from zerver.lib.request import JsonableError
from zerver.models import Realm, UserProfile

def check_valid_emoji(realm, emoji_name):
    # type: (Realm, Text) -> None
    if emoji_name in set(realm.get_emoji().keys()):
        return
    if emoji_name in name_to_codepoint:
        return
    raise JsonableError(_("Emoji '%s' does not exist" % (emoji_name,)))

def check_emoji_admin(user_profile):
    # type: (UserProfile) -> None
    if user_profile.realm.add_emoji_by_admins_only and not user_profile.is_realm_admin:
        raise JsonableError(_("Must be a realm administrator"))

def check_valid_emoji_name(emoji_name):
    # type: (Text) -> None
    if re.match('^[0-9a-zA-Z.\-_]+(?<![.\-_])$', emoji_name):
        return
    raise JsonableError(_("Invalid characters in emoji name"))
