import re
from typing import Any, List, Match

from markdown import Markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from typing_extensions import override

from zerver.lib.markdown.priorities import PREPROCESSOR_PRIORITES

# There is a lot of duplicated code between this file and
# help_settings_links.py. So if you're making a change here consider making
# it there as well.

REGEXP = re.compile(r"\{relative\|(?P<link_type>.*?)\|(?P<key>.*?)\}")

gear_info = {
    # The pattern is key: [name, link]
    # key is from REGEXP: `{relative|gear|key}`
    # name is what the item is called in the gear menu: `Select **name**.`
    # link is used for relative links: `Select [name](link).`
    "channel-settings": [
        '<i class="zulip-icon zulip-icon-hash"></i> Channel settings',
        "/#channels/subscribed",
    ],
    "settings": [
        '<i class="zulip-icon zulip-icon-tool"></i> Personal Settings',
        "/#settings/profile",
    ],
    "organization-settings": [
        '<i class="zulip-icon zulip-icon-building"></i> Organization settings',
        "/#organization/organization-profile",
    ],
    "group-settings": [
        '<i class="zulip-icon zulip-icon-user-cog"></i> Group settings',
        "/#groups/your",
    ],
    "stats": ['<i class="zulip-icon zulip-icon-bar-chart"></i> Usage statistics', "/stats"],
    "integrations": ['<i class="zulip-icon-git-pull-request"></i> Integrations', "/integrations/"],
    "plans": ['<i class="zulip-icon zulip-icon-rocket"></i> Plans and pricing', "/plans/"],
    "billing": ['<i class="zulip-icon zulip-icon-credit-card"></i> Billing', "/billing/"],
    "about-zulip": ["About Zulip", "/#about-zulip"],
}

gear_instructions = """
1. Click on the **gear** (<i class="zulip-icon zulip-icon-gear"></i>) icon in
   the upper right corner of the web or desktop app.

1. Select {item}.
"""


def gear_handle_match(key: str) -> str:
    if relative_help_links:
        item = f"[{gear_info[key][0]}]({gear_info[key][1]})"
    else:
        item = f"**{gear_info[key][0]}**"
    return gear_instructions.format(item=item)


help_info = {
    # The pattern is key: [name, link]
    # key is from REGEXP: `{relative|help|key}`
    # name is what the item is called in the help menu: `Select **name**.`
    # link is used for relative links: `Select [name](link).`
    "keyboard-shortcuts": [
        '<i class="zulip-icon zulip-icon-keyboard"></i> Keyboard shortcuts',
        "/#keyboard-shortcuts",
    ],
    "message-formatting": [
        '<i class="zulip-icon zulip-icon-edit"></i> Message formatting',
        "/#message-formatting",
    ],
    "search-filters": [
        '<i class="zulip-icon zulip-icon-manage-search"></i> Search filters',
        "/#search-operators",
    ],
    "about-zulip": [
        '<i class="zulip-icon zulip-icon-info"></i> About Zulip',
        "/#about-zulip",
    ],
}

help_instructions = """
1. Click on the **Help menu** (<i class="zulip-icon zulip-icon-help"></i>) icon
   in the upper right corner of the app.

1. Select {item}.
"""


def help_handle_match(key: str) -> str:
    if relative_help_links:
        item = f"[{help_info[key][0]}]({help_info[key][1]})"
    else:
        item = f"**{help_info[key][0]}**"
    return help_instructions.format(item=item)


channel_info = {
    "all": ["All channels", "/#channels/all"],
}

channel_all_instructions = """
1. Click on the **gear** (<i class="zulip-icon zulip-icon-gear"></i>) icon in
   the upper right corner of the web or desktop app.

1. Select <i class="zulip-icon zulip-icon-hash"></i> **Channel settings**.

1. Click {item} in the upper left.
"""


def channel_handle_match(key: str) -> str:
    if relative_help_links:
        item = f"[{channel_info[key][0]}]({channel_info[key][1]})"
    else:
        item = f"**{channel_info[key][0]}**"
    return channel_all_instructions.format(item=item)


group_info = {
    "all": ["All groups", "/#groups/all"],
}

group_all_instructions = """
1. Click on the **gear** (<i class="zulip-icon zulip-icon-gear"></i>) icon in
   the upper right corner of the web or desktop app.

1. Select <i class="zulip-icon zulip-icon-user-cog"></i> **Group settings**.

1. Click {item} in the upper left.
"""


def group_handle_match(key: str) -> str:
    if relative_help_links:
        item = f"[{group_info[key][0]}]({group_info[key][1]})"
    else:
        item = f"**{group_info[key][0]}**"
    return group_all_instructions.format(item=item)


draft_instructions = """
1. Click on <i class="fa fa-pencil"></i> **Drafts** in the left sidebar.
"""

scheduled_instructions = """
1. Click on <i class="fa fa-calendar"></i> **Scheduled messages** in the left
   sidebar. If you do not see this link, you have no scheduled messages.
"""

recent_instructions = """
1. Click on <i class="fa fa-clock-o"></i> **Recent conversations** in the left
   sidebar, or use the <kbd>T</kbd> keyboard shortcut..
"""

all_instructions = """
1. Click on <i class="fa fa-align-left"></i> **Combined feed** in the left
   sidebar, or use the <kbd>A</kbd> keyboard shortcut.
"""

starred_instructions = """
1. Click on <i class="fa fa-star"></i> **Starred messages** in the left
   sidebar, or by [searching](/help/search-for-messages) for `is:starred`.
"""

direct_instructions = """
1. In the left sidebar, click the **Direct message feed**
   (<i class="fa fa-align-right"></i>) icon to the right of the
   **Direct messages** label, or use the <kbd>Shift</kbd> + <kbd>P</kbd>
   keyboard shortcut.
"""

inbox_instructions = """
1. Click on <i class="zulip-icon zulip-icon-inbox"></i> **Inbox** in the left
   sidebar, or use the <kbd>Shift</kbd> + <kbd>I</kbd> keyboard shortcut.
"""

message_info = {
    "drafts": ["Drafts", "/#drafts", draft_instructions],
    "scheduled": ["Scheduled messages", "/#scheduled", scheduled_instructions],
    "recent": ["Recent conversations", "/#recent", recent_instructions],
    "all": ["Combined feed", "/#feed", all_instructions],
    "starred": ["Starred messages", "/#narrow/is/starred", starred_instructions],
    "direct": ["Direct message feed", "/#narrow/is/dm", direct_instructions],
    "inbox": ["Inbox", "/#inbox", inbox_instructions],
}


def message_handle_match(key: str) -> str:
    if relative_help_links:
        return f"1. Go to [{message_info[key][0]}]({message_info[key][1]})."
    else:
        return message_info[key][2]


LINK_TYPE_HANDLERS = {
    "gear": gear_handle_match,
    "channel": channel_handle_match,
    "message": message_handle_match,
    "help": help_handle_match,
    "group": group_handle_match,
}


class RelativeLinksHelpExtension(Extension):
    @override
    def extendMarkdown(self, md: Markdown) -> None:
        """Add RelativeLinksHelpExtension to the Markdown instance."""
        md.registerExtension(self)
        md.preprocessors.register(
            RelativeLinks(), "help_relative_links", PREPROCESSOR_PRIORITES["help_relative_links"]
        )


relative_help_links: bool = False


def set_relative_help_links(value: bool) -> None:
    global relative_help_links
    relative_help_links = value


class RelativeLinks(Preprocessor):
    @override
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
        return LINK_TYPE_HANDLERS[match.group("link_type")](match.group("key"))


def makeExtension(*args: Any, **kwargs: Any) -> RelativeLinksHelpExtension:
    return RelativeLinksHelpExtension(*args, **kwargs)
