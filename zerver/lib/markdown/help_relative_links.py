import re
from typing import Any, List, Match

from markdown import Markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

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
    "manage-streams": ['<i class="fa fa-exchange"></i> Manage streams', "/#streams/subscribed"],
    "settings": ['<i class="fa fa-wrench"></i> Personal Settings', "/#settings/profile"],
    "organization-settings": [
        '<i class="fa fa-bolt"></i> Organization settings',
        "/#organization/organization-profile",
    ],
    "integrations": ['<i class="fa fa-github"></i> Integrations', "/integrations/"],
    "stats": ['<i class="fa fa-bar-chart"></i> Usage statistics', "/stats"],
    "plans": ['<i class="fa fa-rocket"></i> Plans and pricing', "/plans/"],
    "billing": ['<i class="fa fa-credit-card"></i> Billing', "/billing/"],
    "keyboard-shortcuts": [
        '<i class="fa fa-keyboard-o"></i> Keyboard shortcuts (?)',
        "/#keyboard-shortcuts",
    ],
    "message-formatting": [
        '<i class="fa fa-pencil"></i> Message formatting',
        "/#message-formatting",
    ],
    "search-filters": ['<i class="fa fa-search"></i> Search filters', "/#search-operators"],
    "about-zulip": ["About Zulip", "/#about-zulip"],
}

gear_instructions = """
1. Click on the **gear** (<i class="fa fa-cog"></i>) icon in the upper
   right corner of the web or desktop app.

1. Select {item}.
"""


def gear_handle_match(key: str) -> str:
    if relative_help_links:
        item = f"[{gear_info[key][0]}]({gear_info[key][1]})"
    else:
        item = f"**{gear_info[key][0]}**"
    return gear_instructions.format(item=item)


stream_info = {
    "all": ["All streams", "/#streams/all"],
    "subscribed": ["Subscribed streams", "/#streams/subscribed"],
}

stream_instructions_no_link = """
1. Click on the **gear** (<i class="fa fa-cog"></i>) icon in the upper
   right corner of the web or desktop app.

1. Click **Manage streams**.
"""


def stream_handle_match(key: str) -> str:
    if relative_help_links:
        return f"1. Go to [{stream_info[key][0]}]({stream_info[key][1]})."
    if key == "all":
        return stream_instructions_no_link + "\n\n1. Click **All streams** in the upper left."
    return stream_instructions_no_link


draft_instructions = """
1. Click on <i class="fa fa-pencil"></i> **Drafts** in the left sidebar.
"""

scheduled_instructions = """
1. Click on <i class="fa fa-calendar"></i> **Scheduled messages** in the left
   sidebar. If you do not see this link, you have no scheduled messages.
"""

recent_instructions = """
1. Click on <i class="fa fa-clock-o"></i> **Recent conversations** in the left
   sidebar.
"""

all_instructions = """
1. Click on <i class="fa fa-align-left"></i> **All messages** in the left
   sidebar or use the <kbd>A</kbd> keyboard shortcut.
"""

starred_instructions = """
1. Click on <i class="fa fa-star"></i> **Starred messages** in the left
   sidebar, or by [searching](/help/search-for-messages) for `is:starred`.
"""

direct_instructions = """
1. In the left sidebar, click the **All direct messages**
   (<i class="fa fa-align-right"></i>) icon to the right of the
   **Direct messages** label, or use the <kbd>Shift</kbd> + <kbd>P</kbd>
   keyboard shortcut.
"""

message_info = {
    "drafts": ["Drafts", "/#drafts", draft_instructions],
    "scheduled": ["Scheduled messages", "/#scheduled", scheduled_instructions],
    "recent": ["Recent conversations", "/#recent", recent_instructions],
    "all": ["All messages", "/#all_messages", all_instructions],
    "starred": ["Starred messages", "/#narrow/is/starred", starred_instructions],
    "direct": ["All direct messages", "/#narrow/is/dm", direct_instructions],
}


def message_handle_match(key: str) -> str:
    if relative_help_links:
        return f"1. Go to [{message_info[key][0]}]({message_info[key][1]})."
    else:
        return message_info[key][2]


LINK_TYPE_HANDLERS = {
    "gear": gear_handle_match,
    "stream": stream_handle_match,
    "message": message_handle_match,
}


class RelativeLinksHelpExtension(Extension):
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
