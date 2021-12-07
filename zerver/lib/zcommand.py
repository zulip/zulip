from typing import Any, Dict

from django.utils.translation import gettext as _

from zerver.lib.actions import do_change_user_setting
from zerver.lib.exceptions import JsonableError
from zerver.models import UserProfile


def process_zcommands(content: str, user_profile: UserProfile) -> Dict[str, Any]:
    def change_mode_setting(
        command: str, switch_command: str, setting: str, setting_value: int
    ) -> str:
        msg = (
            "Changed to {command} mode! To revert "
            "{command} mode, type `/{switch_command}`.".format(
                command=command,
                switch_command=switch_command,
            )
        )
        do_change_user_setting(
            user_profile=user_profile,
            setting_name=setting,
            setting_value=setting_value,
            acting_user=user_profile,
        )
        return msg

    if not content.startswith("/"):
        raise JsonableError(_("There should be a leading slash in the zcommand."))
    command = content[1:]

    if command == "ping":
        return {}
    elif command == "night":
        if user_profile.color_scheme == UserProfile.COLOR_SCHEME_NIGHT:
            return dict(msg="You are still in dark mode.")
        return dict(
            msg=change_mode_setting(
                command="dark",
                switch_command="light",
                setting="color_scheme",
                setting_value=UserProfile.COLOR_SCHEME_NIGHT,
            )
        )
    elif command == "day":
        if user_profile.color_scheme == UserProfile.COLOR_SCHEME_LIGHT:
            return dict(msg="You are still in light mode.")
        return dict(
            msg=change_mode_setting(
                command="light",
                switch_command="dark",
                setting="color_scheme",
                setting_value=UserProfile.COLOR_SCHEME_LIGHT,
            )
        )
    elif command == "fluid-width":
        if user_profile.fluid_layout_width:
            return dict(msg="You are still in fluid width mode.")
        return dict(
            msg=change_mode_setting(
                command=command,
                switch_command="fixed-width",
                setting="fluid_layout_width",
                setting_value=True,
            )
        )
    elif command == "fixed-width":
        if not user_profile.fluid_layout_width:
            return dict(msg="You are still in fixed width mode.")
        return dict(
            msg=change_mode_setting(
                command=command,
                switch_command="fluid-width",
                setting="fluid_layout_width",
                setting_value=False,
            )
        )
    raise JsonableError(_("No such command: {}").format(command))
