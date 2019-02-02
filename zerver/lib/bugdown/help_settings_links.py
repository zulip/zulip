import re
import markdown
from typing import Any, Dict, List, Optional
from typing.re import Match
from markdown.preprocessors import Preprocessor

# There is a lot of duplicated code between this file and
# help_relative_links.py. So if you're making a change here consider making
# it there as well.

REGEXP = re.compile(r'\{settings_tab\|(?P<setting_identifier>.*?)\}')

link_mapping = {
    # a mapping from the setting identifier that is the same as the final URL
    # breadcrumb to that setting to the name of its setting type, the setting
    # name as it appears in the user interface, and a relative link that can
    # be used to get to that setting
    'your-account': ['Settings', 'Your account', '/#settings/your-account'],
    'display-settings': ['Settings', 'Display settings', '/#settings/display-settings'],
    'notifications': ['Settings', 'Notifications', '/#settings/notifications'],
    'your-bots': ['Settings', 'Your bots', '/#settings/your-bots'],
    'alert-words': ['Settings', 'Alert words', '/#settings/alert-words'],
    'uploaded-files': ['Settings', 'Uploaded files', '/#settings/uploaded-files'],
    'muted-topics': ['Settings', 'Muted topics', '/#settings/muted-topics'],

    'organization-profile': ['Manage organization', 'Organization profile',
                             '/#organization/organization-profile'],
    'organization-settings': ['Manage organization', 'Organization settings',
                              '/#organization/organization-settings'],
    'organization-permissions': ['Manage organization', 'Organization permissions',
                                 '/#organization/organization-permissions'],
    'emoji-settings': ['Manage organization', 'Custom emoji',
                       '/#organization/emoji-settings'],
    'auth-methods': ['Manage organization', 'Authentication methods',
                     '/#organization/auth-methods'],
    'user-groups-admin': ['Manage organization', 'User groups',
                          '/#organization/user-groups-admin'],
    'user-list-admin': ['Manage organization', 'Users', '/#organization/user-list-admin'],
    'deactivated-users-admin': ['Manage organization', 'Deactivated users',
                                '/#organization/deactivated-users-admin'],
    'bot-list-admin': ['Manage organization', 'Bots', '/#organization/bot-list-admin'],
    'default-streams-list': ['Manage organization', 'Default streams',
                             '/#organization/default-streams-list'],
    'filter-settings': ['Manage organization', 'Linkifiers',
                        '/#organization/filter-settings'],
    'profile-field-settings': ['Manage organization', 'Custom profile fields',
                               '/#organization/profile-field-settings'],
    'invites-list-admin': ['Manage organization', 'Invitations',
                           '/#organization/invites-list-admin'],
}

settings_markdown = """
1. From your desktop, click on the **gear**
   (<i class="fa fa-cog"></i>) in the upper right corner.

1. Select **%(setting_type_name)s**.

1. On the left, click %(setting_reference)s.
"""


class SettingHelpExtension(markdown.Extension):
    def extendMarkdown(self, md: markdown.Markdown, md_globals: Dict[str, Any]) -> None:
        """ Add SettingHelpExtension to the Markdown instance. """
        md.registerExtension(self)
        md.preprocessors.add('setting', Setting(), '_begin')

relative_settings_links = None  # type: Optional[bool]

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
                    text = [preceding] + text + [following]
                    lines = lines[:loc] + text + lines[loc+1:]
                    break
            else:
                done = True
        return lines

    def handleMatch(self, match: Match[str]) -> str:
        setting_identifier = match.group('setting_identifier')
        setting_type_name = link_mapping[setting_identifier][0]
        setting_name = link_mapping[setting_identifier][1]
        setting_link = link_mapping[setting_identifier][2]
        if relative_settings_links:
            return "1. Go to [%s](%s)." % (setting_name, setting_link)
        return settings_markdown % {'setting_type_name': setting_type_name,
                                    'setting_reference': "**%s**" % (setting_name,)}

def makeExtension(*args: Any, **kwargs: Any) -> SettingHelpExtension:
    return SettingHelpExtension(*args, **kwargs)
