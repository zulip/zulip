from typing import Any, Dict

from django.utils.translation import ugettext as _

from zerver.lib.actions import do_set_user_display_setting
from zerver.lib.exceptions import JsonableError
from zerver.models import UserProfile


def process_zcommands(content: str, user_profile: UserProfile) -> Dict[str, Any]:
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

    def change_theme_setting(command: str) -> str:
        command_scheme_map = {
            'day': UserProfile.COLOR_SCHEME_LIGHT,
            'night': UserProfile.COLOR_SCHEME_NIGHT,
            'auto': UserProfile.COLOR_SCHEME_AUTOMATIC
        }

        scheme_command_map = {
            UserProfile.COLOR_SCHEME_LIGHT: 'theme day',
            UserProfile.COLOR_SCHEME_NIGHT: 'theme night',
            UserProfile.COLOR_SCHEME_AUTOMATIC: 'theme auto'
        }

        new_color_scheme = command_scheme_map.get(command)
        switch_command = scheme_command_map.get(user_profile.color_scheme)

        if new_color_scheme is None or switch_command is None:
            raise JsonableError(_('Invalid parameter for /theme zcommand.'))

        if user_profile.color_scheme == new_color_scheme:
            return 'You are still in {command} mode.'.format(command=command)

        msg = 'Changed to {command} mode! To revert ' \
            'to previous settings, type `/{switch_command}`.'.format(
                command=command,
                switch_command=switch_command,
            )
        do_set_user_display_setting(user_profile=user_profile,
                                    setting_name='color_scheme',
                                    setting_value=new_color_scheme)
        return msg

    if not content.startswith('/'):
        raise JsonableError(_('There should be a leading slash in the zcommand.'))
    command = content.split(' ')[0][1:]
    command_parameters = (content.split(' ')[1:] + [''] * 5)[:5]

    if command == 'ping':
        return {}
    elif command == 'night' or command == 'day' or command == 'auto':
        return dict(msg=change_theme_setting(command=command))
    elif command == 'theme':
        return dict(msg=change_theme_setting(command=command_parameters[0]))
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
    raise JsonableError(_('No such command: {}').format(command))
