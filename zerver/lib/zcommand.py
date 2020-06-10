from typing import Any, Dict

from django.utils.translation import ugettext as _

from zerver.lib.actions import do_set_user_display_setting
from zerver.lib.exceptions import JsonableError
from zerver.models import UserProfile


def process_zcommands(content: str, user_profile: UserProfile) -> Dict[str, Any]:
    def change_mode_setting(command: str, switch_command: str,
                            setting: str, setting_value: bool) -> str:
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
        return dict()
    elif command == 'night':
        if user_profile.night_mode:
            return dict(msg='You are still in night mode.')
        return dict(msg=change_mode_setting(command=command,
                                            switch_command='day',
                                            setting='night_mode',
                                            setting_value=True))
    elif command == 'day':
        if not user_profile.night_mode:
            return dict(msg='You are still in day mode.')
        return dict(msg=change_mode_setting(command=command,
                                            switch_command='night',
                                            setting='night_mode',
                                            setting_value=False))
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
    raise JsonableError(_('No such command: %s') % (command,))
