from typing import Any

from django.utils.translation import gettext as _

from zerver.actions.user_settings import do_change_user_setting
from zerver.lib.exceptions import JsonableError
from zerver.models import UserProfile


def process_zcommands(content: str, user_profile: UserProfile) -> dict[str, Any]:
    def change_mode_setting(
        setting_name: str, switch_command: str, setting: str, setting_value: int
    ) -> str:
        msg = f"Changed to {setting_name}! To revert {setting_name}, type `/{switch_command}`."
        do_change_user_setting(
            user_profile=user_profile,
            setting_name=setting,
            setting_value=setting_value,
            acting_user=user_profile,
        )
        return msg

    if not content.startswith("/"):
        raise JsonableError(_("There should be a leading slash in the zcommand."))
    command = content.removeprefix("/")

    if command == "ping":
        return {}
    elif command == "dark":
        if user_profile.color_scheme == UserProfile.COLOR_SCHEME_DARK:
            return dict(msg="You are still in dark theme.")
        return dict(
            msg=change_mode_setting(
                setting_name="dark theme",
                switch_command="light",
                setting="color_scheme",
                setting_value=UserProfile.COLOR_SCHEME_DARK,
            )
        )
    elif command == "light":
        if user_profile.color_scheme == UserProfile.COLOR_SCHEME_LIGHT:
            return dict(msg="You are still in light theme.")
        return dict(
            msg=change_mode_setting(
                setting_name="light theme",
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
                setting_name="fluid-width mode",
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
                setting_name="fixed-width mode",
                switch_command="fluid-width",
                setting="fluid_layout_width",
                setting_value=False,
            )
        )
    

    elif command == "realm_users":
        from zerver.models.meetings import get_realm_users_list
        msg = get_realm_users_list(user_profile.realm)
        return dict(msg=msg)
    elif command.startswith("channel_users"):
        from zerver.models.meetings import get_channel_users_list
        parts = command.split()
        channel_name = parts[1] if len(parts) > 1 else "test-channel"
        msg = get_channel_users_list(user_profile, channel_name)
        return dict(msg=msg)
    elif command.startswith("add "):
        from zerver.models.meetings import add_persons_to_channel_by_id
        parts = command.split()
        if len(parts) < 3:
            raise JsonableError(_("Usage: /add <channel_name> <user_id1> <user_id2> ..."))
        
        try:
            channel_name = parts[1]
            user_ids = [int(uid) for uid in parts[2:]]
        except ValueError:
            raise JsonableError(_("Usage: /add <channel_name> <user_id1> <user_id2> ..."))
            
        msg = add_persons_to_channel_by_id(user_profile, channel_name, user_ids)
        return dict(msg=msg)

    raise JsonableError(_("No such command: {command}").format(command=command))
