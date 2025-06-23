import re
from re import Match
from typing import Any

from markdown import Markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from typing_extensions import override

from zerver.lib.markdown.priorities import PREPROCESSOR_PRIORITIES

# There is a lot of duplicated code between this file and
# help_relative_links.py. So if you're making a change here consider making
# it there as well.

REGEXP = re.compile(r"\{settings_tab\|(?P<setting_identifier>.*?)\}")


# If any changes to this link mapping are made,
# `help-beta/src/components/NavigationSteps.astro` should be updated accordingly.
# This manual update mechanism will cease to exist once we have switched to the
# help-beta system.
link_mapping = {
    # a mapping from the setting identifier that is the same as the final URL
    # breadcrumb to that setting to the name of its setting type, the setting
    # name as it appears in the user interface, and a relative link that can
    # be used to get to that setting
    "profile": ["Personal settings", "Profile", "/#settings/profile"],
    "account-and-privacy": [
        "Personal settings",
        "Account & privacy",
        "/#settings/account-and-privacy",
    ],
    "preferences": ["Personal settings", "Preferences", "/#settings/preferences"],
    "notifications": ["Personal settings", "Notifications", "/#settings/notifications"],
    "your-bots": ["Personal settings", "Bots", "/#settings/your-bots"],
    "alert-words": ["Personal settings", "Alert words", "/#settings/alert-words"],
    "uploaded-files": ["Personal settings", "Uploaded files", "/#settings/uploaded-files"],
    "topics": ["Personal settings", "Topics", "/#settings/topics"],
    "muted-users": ["Personal settings", "Muted users", "/#settings/muted-users"],
    "organization-profile": [
        "Organization settings",
        "Organization profile",
        "/#organization/organization-profile",
    ],
    "organization-settings": [
        "Organization settings",
        "Organization settings",
        "/#organization/organization-settings",
    ],
    "organization-permissions": [
        "Organization settings",
        "Organization permissions",
        "/#organization/organization-permissions",
    ],
    "default-user-settings": [
        "Organization settings",
        "Default user settings",
        "/#organization/organization-level-user-defaults",
    ],
    "emoji-settings": ["Organization settings", "Custom emoji", "/#organization/emoji-settings"],
    "auth-methods": [
        "Organization settings",
        "Authentication methods",
        "/#organization/auth-methods",
    ],
    "users": [
        "Organization settings",
        "Users",
        "/#organization/users/active",
    ],
    "deactivated": [
        "Organization settings",
        "Users",
        "/#organization/users/deactivated",
    ],
    "invitations": [
        "Organization settings",
        "Users",
        "/#organization/users/invitations",
    ],
    "bot-list-admin": [
        "Organization settings",
        "Bots",
        "/#organization/bot-list-admin",
    ],
    "default-channels-list": [
        "Organization settings",
        "Default channels",
        "/#organization/default-channels-list",
    ],
    "linkifier-settings": [
        "Organization settings",
        "Linkifiers",
        "/#organization/linkifier-settings",
    ],
    "playground-settings": [
        "Organization settings",
        "Code playgrounds",
        "/#organization/playground-settings",
    ],
    "profile-field-settings": [
        "Organization settings",
        "Custom profile fields",
        "/#organization/profile-field-settings",
    ],
    "data-exports-admin": [
        "Organization settings",
        "Data exports",
        "/#organization/data-exports-admin",
    ],
}

settings_markdown = """
1. Click on the **gear** (<i class="zulip-icon zulip-icon-gear"></i>) icon in the upper
   right corner of the web or desktop app.

1. Select **{setting_type_name}**.

1. On the left, click {setting_reference}.
"""


def getMarkdown(setting_type_name: str, setting_name: str, setting_link: str) -> str:
    if relative_settings_links:
        relative_link = f"[{setting_name}]({setting_link})"
        # The "Bots" label appears in both Personal and Organization settings
        # in the user interface so we need special text for this setting.
        if setting_name in ["Bots", "Users"]:
            return f"1. Navigate to the {relative_link} \
                    tab of the **{setting_type_name}** menu."
        return f"1. Go to {relative_link}."
    return settings_markdown.format(
        setting_type_name=setting_type_name,
        setting_reference=f"**{setting_name}**",
    )


class SettingHelpExtension(Extension):
    @override
    def extendMarkdown(self, md: Markdown) -> None:
        """Add SettingHelpExtension to the Markdown instance."""
        md.registerExtension(self)
        md.preprocessors.register(Setting(), "setting", PREPROCESSOR_PRIORITIES["setting"])


relative_settings_links: bool = False


def set_relative_settings_links(value: bool) -> None:
    global relative_settings_links
    relative_settings_links = value


class Setting(Preprocessor):
    @override
    def run(self, lines: list[str]) -> list[str]:
        done = False
        while not done:
            for line in lines:
                loc = lines.index(line)
                match = REGEXP.search(line)

                if match:
                    text = [self.handleMatch(match)]
                    # The line that contains the directive to include the macro
                    # may be preceded or followed by text or tags, in that case
                    # we need to make sure that any preceding or following text
                    # stays the same.
                    line_split = REGEXP.split(line, maxsplit=0)
                    preceding = line_split[0]
                    following = line_split[-1]
                    text = [preceding, *text, following]
                    lines = lines[:loc] + text + lines[loc + 1 :]
                    break
            else:
                done = True
        return lines

    def handleMatch(self, match: Match[str]) -> str:
        setting_identifier = match.group("setting_identifier")
        return getMarkdown(*link_mapping[setting_identifier])


def makeExtension(*args: Any, **kwargs: Any) -> SettingHelpExtension:
    return SettingHelpExtension(*args, **kwargs)
