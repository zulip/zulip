import json
from typing import Any, Dict, Optional

import requests
from django.utils.translation import ugettext as _

from zerver.lib.actions import (
    do_set_user_display_setting,
    internal_send_huddle_message,
    internal_send_stream_message,
    send_message_moved_breadcrumbs,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.home import get_giphy_api_key
from zerver.lib.streams import access_stream_by_name
from zerver.lib.topic import user_message_exists_for_topic
from zerver.models import UserProfile


def process_zcommands(content: str,
                      data: Optional[Dict[str, Any]],
                      user_profile: UserProfile) -> Dict[str, Any]:
    def change_mode_setting(command: str, switch_command: str,
                            setting: str, setting_value: int) -> str:
        msg = 'Changed to {command} mode! To revert ' \
            '{command} mode, type `/{switch_command}`.'.format(
                command=command,
                switch_command=switch_command,
            )
        do_set_user_display_setting(user_profile=user_profile,
                                    setting_name=setting,
                                    setting_value=setting_value)
        return msg

    if not content.startswith('/'):
        raise JsonableError(_('There should be a leading slash in the zcommand.'))
    command = content[1:]

    if command == 'ping':
        return {}
    elif command == 'night':
        if user_profile.color_scheme == UserProfile.COLOR_SCHEME_NIGHT:
            return dict(msg='You are still in night mode.')
        return dict(msg=change_mode_setting(command=command,
                                            switch_command='day',
                                            setting='color_scheme',
                                            setting_value=UserProfile.COLOR_SCHEME_NIGHT))
    elif command == 'day':
        if user_profile.color_scheme == UserProfile.COLOR_SCHEME_LIGHT:
            return dict(msg='You are still in day mode.')
        return dict(msg=change_mode_setting(command=command,
                                            switch_command='night',
                                            setting='color_scheme',
                                            setting_value=UserProfile.COLOR_SCHEME_LIGHT))
    elif command == 'fluid-width':
        if user_profile.fluid_layout_width:
            return dict(msg='You are still in fluid width mode.')
        return dict(msg=change_mode_setting(command=command,
                                            switch_command='fixed-width',
                                            setting='fluid_layout_width',
                                            setting_value=True))
    elif command == 'fixed-width':
        if not user_profile.fluid_layout_width:
            return dict(msg='You are still in fixed width mode.')
        return dict(msg=change_mode_setting(command=command,
                                            switch_command='fluid-width',
                                            setting='fluid_layout_width',
                                            setting_value=False))
    elif command == 'digress':
        data_keys = [
            "old_stream",
            "old_topic",
            "new_stream",
            "new_topic",
        ]
        if not data or not all(key in data for key in data_keys):
            raise JsonableError(_('Invalid data.'))

        if data["old_stream"] == data["new_stream"] and data["old_topic"] == data["new_topic"]:
            return dict(msg=_('Cannot digress to the same thread.'))

        (old_stream, ignored_old_stream_sub) = access_stream_by_name(
            user_profile, data["old_stream"])

        (new_stream, ignored_new_stream_sub) = access_stream_by_name(
            user_profile, data["new_stream"])

        old_topic_exists = user_message_exists_for_topic(
            user_profile=user_profile,
            recipient_id=old_stream.recipient_id,
            topic_name=data["old_topic"],
        )

        if not old_topic_exists:
            return dict(
                msg=_('Old topic #**{}>{}** does not exist.').format(data["old_stream"], data["old_topic"])
            )

        old_thread_notification_string = _("{user} will be talking on the new topic: {new_location}")
        new_thread_notification_string = _("{user} digressed this from old topic: {old_location}")
        send_message_moved_breadcrumbs(user_profile,
                                       old_stream,
                                       data["old_topic"],
                                       old_thread_notification_string,
                                       True,
                                       new_stream,
                                       data["new_topic"],
                                       new_thread_notification_string,
                                       True)
        return {}
    elif command == 'giphy':
        if data is None:
            raise JsonableError(_('Invalid data.'))
        api_key = get_giphy_api_key()
        text = data.get('text')
        stream_name = data.get('stream')
        topic = data.get('topic')
        recipient = data.get('recipient')
        if not api_key:
            raise JsonableError(_('Please contact administrator to enable this feature.'))
        payload = {
            'api_key': api_key,
            # Converted to str to fix mypy.
            'tag': str(text),
            'random_id': str(user_profile.id),
        }
        response = requests.get('http://api.giphy.com/v1/gifs/random', params=payload)
        if response.status_code == 200:
            giphy_url = json.loads(response.text)['data']['images']['downsized_large']['url']
            content = f'[{text}]({giphy_url})'
            if stream_name and topic:
                (stream, ignored_old_stream_sub) = access_stream_by_name(user_profile, stream_name)
                internal_send_stream_message(
                    user_profile.realm,
                    user_profile,
                    stream,
                    topic,
                    content
                )
            elif recipient:
                internal_send_huddle_message(
                    user_profile.realm,
                    user_profile,
                    recipient.split(','),
                    content
                )
            else:
                raise JsonableError(_('Invalid data.'))
        return {}
    raise JsonableError(_('No such command: {}').format(command))
