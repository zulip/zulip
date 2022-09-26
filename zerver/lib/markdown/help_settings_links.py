import re
from typing import Any, List, Match

from markdown import Markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

from zerver.lib.markdown.priorities import PREPROCESSOR_PRIORITES

# There is a lot of duplicated code between this file and
# help_relative_links.py. So if you're making a change here consider making
# it there as well.

REGEXP = re.compile(r"\{settings_tab\|(?P<setting_identifier>.*?)\}")

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
    "display-settings": ["Personal settings", "Display settings", "/#settings/display-settings"],
    "notifications": ["Personal settings", "Notifications", "/#settings/notifications"],
    "your-bots": ["Personal settings", "Bots", "/#settings/your-bots"],
    "alert-words": ["Personal settings", "Alert words", "/#settings/alert-words"],
    "uploaded-files": ["Personal settings", "Uploaded files", "/#settings/uploaded-files"],
    "muted-topics": ["Personal settings", "Muted topics", "/#settings/muted-topics"],
    "muted-users": ["Personal settings", "Muted users", "/#settings/muted-users"],
    "organization-profile": [
        "Manage organization",
        "Organization profile",
        "/#organization/organization-profile",
    ],
    "organization-settings": [
        "Manage organization",
        "Organization settings",
        "/#organization/organization-settings",
    ],
    "organization-permissions": [
        "Manage organization",
        "Organization permissions",
        "/#organization/organization-permissions",
    ],
    "default-user-settings": [
        "Manage organization",
        "Default user settings",
        "/#organization/organization-level-user-defaults",
    ],
    "emoji-settings": ["Manage organization", "Custom emoji", "/#organization/emoji-settings"],
    "auth-methods": [
        "Manage organization",
        "Authentication methods",
        "/#organization/auth-methods",
    ],
    "user-groups-admin": ["Manage organization", "User groups", "/#organization/user-groups-admin"],
    "user-list-admin": ["Manage organization", "Users", "/#organization/user-list-admin"],
    "deactivated-users-admin": [
        "Manage organization",
        "Deactivated users",
        "/#organization/deactivated-users-admin",
    ],
    "bot-list-admin": ["Manage organization", "Bots", "/#organization/bot-list-admin"],
    "default-streams-list": [
        "Manage organization",
        "Default streams",
        "/#organization/default-streams-list",
    ],
    "linkifier-settings": [
        "Manage organization",
        "Linkifiers",
        "/#organization/linkifier-settings",
    ],
    "playground-settings": [
        "Manage organization",
        "Code playgrounds",
        "/#organization/playground-settings",
    ],
    "profile-field-settings": [
        "Manage organization",
        "Custom profile fields",
        "/#organization/profile-field-settings",
    ],
    "invites-list-admin": [
        "Manage organization",
        "Invitations",
        "/#organization/invites-list-admin",
    ],
    "data-exports-admin": [
        "Manage organization",
        "Data exports",
        "/#organization/data-exports-admin",
    ],
}

settings_markdown = """
1. Click on the **gear** (<i class="fa fa-cog"></i>) icon in the upper
   right corner of the web or desktop app.

1. Select **{setting_type_name}**.

1. On the left, click {setting_reference}.
"""


class SettingHelpExtension(Extension):
    def extendMarkdown(self, md: Markdown) -> None:
        """Add SettingHelpExtension to the Markdown instance."""
        md.registerExtension(self)
        md.preprocessors.register(Setting(), "setting", PREPROCESSOR_PRIORITES["setting"])


relative_settings_links: bool = False


def set_relative_settings_links(value: bool) -> None:
    global relative_settings_links
    relative_settings_links = value


class Setting(Preprocessor):
    def run(self, lines: List[str]) -> List[str]:
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
        setting_type_name = link_mapping[setting_identifier][0]
        setting_name = link_mapping[setting_identifier][1]
        setting_link = link_mapping[setting_identifier][2]
        if relative_settings_links:
            return f"1. Go to [{setting_name}]({setting_link})."
        return settings_markdown.format(
            setting_type_name=setting_type_name,
            setting_reference=f"**{setting_name}**",
        )


def makeExtension(*args: Any, **kwargs: Any) -> SettingHelpExtension:
    return SettingHelpExtension(*args, **kwargs)
