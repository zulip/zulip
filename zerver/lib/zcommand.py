from typing import Any, Dict
from django.utils.translation import ugettext as _

from zerver.models import UserProfile
from zerver.lib.actions import do_set_user_display_setting
from zerver.lib.exceptions import JsonableError

def process_zcommands(content: str, user_profile: UserProfile) -> Dict[str, Any]:
    if not content.startswith('/'):
        raise JsonableError(_('There should be a leading slash in the zcommand.'))
    command = content[1:]

    if command == 'ping':
        ret = dict()  # type: Dict[str, Any]
        return ret

    if command == 'night':
        if user_profile.night_mode:
            msg = 'You are still in night mode.'
        else:
            msg = 'Changed to night mode! To revert night mode, type `/day`.'
            do_set_user_display_setting(user_profile, 'night_mode', True)
        ret = dict(msg=msg)
        return ret

    if command == 'day':
        if user_profile.night_mode:
            msg = 'Changed to day mode! To revert day mode, type `/night`.'
            do_set_user_display_setting(user_profile, 'night_mode', False)
        else:
            msg = 'You are still in day mode.'
        ret = dict(msg=msg)
        return ret

    raise JsonableError(_('No such command: %s') % (command,))
