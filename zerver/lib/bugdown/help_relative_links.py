import re
import markdown
from typing import Any, Dict, List, Optional
from typing.re import Match
from markdown.preprocessors import Preprocessor

# There is a lot of duplicated code between this file and
# help_settings_links.py. So if you're making a change here consider making
# it there as well.

REGEXP = re.compile(r'\{relative\|(?P<link_type>.*?)\|(?P<key>.*?)\}')

gear_info = {
    # The pattern is key: [name, link]
    # key is from REGEXP: `{relative|gear|key}`
    # name is what the item is called in the gear menu: `Select **name**.`
    # link is used for relative links: `Select [name](link).`
    'manage-streams': ['Manage streams', '/#streams/subscribed'],
    'settings': ['Settings', '/#settings/your-account'],
    'manage-organization': ['Manage organization', '/#organization/organization-profile'],
    'integrations': ['Integrations', '/integrations'],
    'stats': ['Statistics', '/stats'],
    'plans': ['Plans and pricing', '/plans'],
    'billing': ['Billing', '/billing'],
    'invite': ['Invite users', '/#invite'],
}

gear_instructions = """
1. From your desktop, click on the **gear**
   (<i class="fa fa-cog"></i>) in the upper right corner.

1. Select %(item)s.
"""

def gear_handle_match(key: str) -> str:
    if relative_help_links:
        item = '[%s](%s)' % (gear_info[key][0], gear_info[key][1])
    else:
        item = '**%s**' % (gear_info[key][0],)
    return gear_instructions % {'item': item}


stream_info = {
    'all': ['All streams', '/#streams/all'],
    'subscribed': ['Your streams', '/#streams/subscribed'],
}

stream_instructions_no_link = """
1. From your desktop, click on the **gear**
   (<i class="fa fa-cog"></i>) in the upper right corner.

1. Click **Manage streams**.
"""

def stream_handle_match(key: str) -> str:
    if relative_help_links:
        return "1. Go to [%s](%s)." % (stream_info[key][0], stream_info[key][1])
    if key == 'all':
        return stream_instructions_no_link + "\n\n1. Click **All streams** in the upper left."
    return stream_instructions_no_link


LINK_TYPE_HANDLERS = {
    'gear': gear_handle_match,
    'stream': stream_handle_match,
}

class RelativeLinksHelpExtension(markdown.Extension):
    def extendMarkdown(self, md: markdown.Markdown, md_globals: Dict[str, Any]) -> None:
        """ Add RelativeLinksHelpExtension to the Markdown instance. """
        md.registerExtension(self)
        md.preprocessors.add('help_relative_links', RelativeLinks(), '_begin')

relative_help_links = None  # type: Optional[bool]

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
                    text = [preceding] + text + [following]
                    lines = lines[:loc] + text + lines[loc+1:]
                    break
            else:
                done = True
        return lines

    def handleMatch(self, match: Match[str]) -> str:
        return LINK_TYPE_HANDLERS[match.group('link_type')](match.group('key'))

def makeExtension(*args: Any, **kwargs: Any) -> RelativeLinksHelpExtension:
    return RelativeLinksHelpExtension(*args, **kwargs)
