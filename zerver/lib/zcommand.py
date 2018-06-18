from typing import Any, Dict, Tuple, Optional
from django.utils.translation import ugettext as _

from zerver.models import UserProfile, get_realm_stream, Stream
from zerver.lib.actions import do_set_user_display_setting
from zerver.lib.exceptions import JsonableError
from zerver.lib.bugdown import MentionData

import re

SUBSCRIBE_REGEX = r'^subscribe[ ]+#\*\*([^*]+)\*\*[ ]+(@\*\*[^*]+\*\*)$'

def get_user_and_stream_subscribe_command(content: str,
                                          realm_id: int) -> Tuple[Optional[Stream],
                                                                  Optional[int]]:
    stream, user_id = None, None
    match = re.search(SUBSCRIBE_REGEX, content)
    if match:
        stream_name, user_mention = match.group(1), match.group(2)

        try:
            stream = get_realm_stream(stream_name=stream_name, realm_id=realm_id)
        except Stream.DoesNotExist:
            pass

        mentioned_user_id = MentionData(realm_id, user_mention).get_user_ids()
        if len(mentioned_user_id) == 1:
            [user_id] = mentioned_user_id
    return stream, user_id

def process_zcommands(content: str, user_profile: UserProfile) -> Dict[str, Any]:
    if not content.startswith('/'):
        raise JsonableError(_('There should be a leading slash in the zcommand.'))
    content = content[1:]

    tokens = content.split(' ')
    command = tokens[0]

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

    if command == 'subscribe':
        stream, user_id = get_user_and_stream_subscribe_command(
            content, user_profile.realm.id)

        if stream and user_id:
            return dict(stream=stream.name, user_id=user_id)

        if not stream and not user_id:
            msg = "Usage: /subscribe #<stream_name> @<user>"
        elif not stream:
            msg = 'A valid stream name is required.'
        else:
            msg = 'A valid user is required.'
        ret = dict(msg=msg)
        return ret

    raise JsonableError(_('No such command: %s') % (command,))
