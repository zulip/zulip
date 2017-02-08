from __future__ import absolute_import
from typing import Text

from django.utils.translation import ugettext as _

from zerver.lib.actions import do_change_full_name
from zerver.lib.request import JsonableError
from zerver.models import UserProfile

def check_change_full_name(user_profile, full_name):
    # type: (UserProfile, Text) -> Text
    """Verifies that the user's proposed full name is valid.  The caller
    is responsible for checking check permissions.  Returns the new
    full name, which may differ from what was passed in (because this
    function strips whitespace)."""
    new_full_name = full_name.strip()
    if len(new_full_name) > UserProfile.MAX_NAME_LENGTH:
        raise JsonableError(_("Name too long!"))
    if list(set(new_full_name).intersection(UserProfile.NAME_INVALID_CHARS)):
        raise JsonableError(_("Invalid characters in name!"))
    do_change_full_name(user_profile, new_full_name)
    return new_full_name
