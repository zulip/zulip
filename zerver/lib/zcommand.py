from typing import Any, Dict, Tuple, Optional
from django.utils.translation import ugettext as _

from zerver.models import UserProfile, get_realm_stream, \
    get_stream_recipient, topic_exists, Stream
from zerver.lib.actions import do_set_user_display_setting
from zerver.lib.exceptions import JsonableError

import re

MUTE_TOPIC_REGEX = r'^mute_topic[ ]+#\*\*([^*]+)\*\*[ ]+([^*]+)$'

def get_stream_and_topic_from_mute_topic_command(content: str,
                                                 realm_id: int) -> Tuple[Optional[str],
                                                                         Optional[str]]:
    stream, topic = None, None
    match = re.search(MUTE_TOPIC_REGEX, content)
    if match:
        stream, topic = match.group(1), match.group(2)
        topic = topic.strip()
    return stream, topic

def get_stream(stream_name: str, realm_id: int) -> Optional[Stream]:
    try:
        return get_realm_stream(stream_name=stream_name, realm_id=realm_id)
    except Stream.DoesNotExist:
        return None

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

    if command == 'mute_topic':
        stream_name, topic = get_stream_and_topic_from_mute_topic_command(
            content, user_profile.realm.id)

        if not stream_name or not topic:
            return dict(msg="Usage: /mute_topic #<stream_name> <topic_name>")

        stream = get_stream(stream_name, user_profile.realm.id)
        if stream:
            if topic_exists(topic, get_stream_recipient(stream.id)):
                return dict(subject=topic, stream=stream.name, type='stream')
            msg = "A valid topic is required."
        else:
            msg = "A valid stream name is required."

        ret = dict(msg=msg)
        return ret

    raise JsonableError(_('No such command: %s') % (command,))
