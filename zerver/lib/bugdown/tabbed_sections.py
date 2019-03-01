import re

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from typing import Any, Dict, Optional, List
import markdown

START_TABBED_SECTION_REGEX = re.compile(r'^\{start_tabs\}$')
END_TABBED_SECTION_REGEX = re.compile(r'^\{end_tabs\}$')
TAB_CONTENT_REGEX = re.compile(r'^\{tab\|\s*(.+?)\s*\}$')

CODE_SECTION_TEMPLATE = """
<div class="code-section {tab_class}" markdown="1">
{nav_bar}
<div class="blocks">
{blocks}
</div>
</div>
""".strip()

NAV_BAR_TEMPLATE = """
<ul class="nav">
{tabs}
</ul>
""".strip()

NAV_LIST_ITEM_TEMPLATE = """
<li data-language="{data_language}">{name}</li>
""".strip()

DIV_TAB_CONTENT_TEMPLATE = """
<div data-language="{data_language}" markdown="1">
{content}
</div>
""".strip()

# If adding new entries here, also check if you need to update
# tabbed-instructions.js
TAB_DISPLAY_NAMES = {
    'desktop-web': 'Desktop/Web',
    'ios': 'iOS',
    'android': 'Android',
    'mac': 'macOS',
    'windows': 'Windows',
    'linux': 'Linux',
    'python': 'Python',
    'js': 'JavaScript',
    'curl': 'curl',
    'zulip-send': 'zulip-send',

    'cloud': 'HipChat Cloud',
    'server': 'HipChat Server or Data Center',
    'stride': 'Stride',

    'send-email-invitations': 'Send email invitations',
    'share-an-invite-link': 'Share an invite link',
    'allow-anyone-to-join': 'Allow anyone to join',
    'restrict-by-email-domain': 'Restrict by email domain',

    'google-hangouts': 'Google Hangouts',
    'zoom': 'Zoom (experimental)',
    'jitsi-on-premise': 'Jitsi on-premise',
}

class TabbedSectionsGenerator(Extension):
    def extendMarkdown(self, md: markdown.Markdown, md_globals: Dict[str, Any]) -> None:
        md.preprocessors.add(
            'tabbed_sections', TabbedSectionsPreprocessor(md, self.getConfigs()), '_end')

class TabbedSectionsPreprocessor(Preprocessor):
    def __init__(self, md: markdown.Markdown, config: Dict[str, Any]) -> None:
        super(TabbedSectionsPreprocessor, self).__init__(md)

    def run(self, lines: List[str]) -> List[str]:
        tab_section = self.parse_tabs(lines)
        while tab_section:
            if 'tabs' in tab_section:
                tab_class = 'has-tabs'
            else:
                tab_class = 'no-tabs'
                tab_section['tabs'] = [{'tab_name': 'null_tab',
                                        'start': tab_section['start_tabs_index']}]
            nav_bar = self.generate_nav_bar(tab_section)
            content_blocks = self.generate_content_blocks(tab_section, lines)
            rendered_tabs = CODE_SECTION_TEMPLATE.format(
                tab_class=tab_class, nav_bar=nav_bar, blocks=content_blocks)

            start = tab_section['start_tabs_index']
            end = tab_section['end_tabs_index'] + 1
            lines = lines[:start] + [rendered_tabs] + lines[end:]
            tab_section = self.parse_tabs(lines)
        return lines

    def generate_content_blocks(self, tab_section: Dict[str, Any], lines: List[str]) -> str:
        tab_content_blocks = []
        for index, tab in enumerate(tab_section['tabs']):
            start_index = tab['start'] + 1
            try:
                # If there are more tabs, we can use the starting index
                # of the next tab as the ending index of the previous one
                end_index = tab_section['tabs'][index + 1]['start']
            except IndexError:
                # Otherwise, just use the end of the entire section
                end_index = tab_section['end_tabs_index']

            content = '\n'.join(lines[start_index:end_index]).strip()
            tab_content_block = DIV_TAB_CONTENT_TEMPLATE.format(
                data_language=tab['tab_name'],
                # Wrapping the content in two newlines is necessary here.
                # If we don't do this, the inner Markdown does not get
                # rendered properly.
                content='\n{}\n'.format(content))
            tab_content_blocks.append(tab_content_block)
        return '\n'.join(tab_content_blocks)

    def generate_nav_bar(self, tab_section: Dict[str, Any]) -> str:
        li_elements = []
        for tab in tab_section['tabs']:
            li = NAV_LIST_ITEM_TEMPLATE.format(
                data_language=tab.get('tab_name'),
                name=TAB_DISPLAY_NAMES.get(tab.get('tab_name')))
            li_elements.append(li)
        return NAV_BAR_TEMPLATE.format(tabs='\n'.join(li_elements))

    def parse_tabs(self, lines: List[str]) -> Optional[Dict[str, Any]]:
        block = {}  # type: Dict[str, Any]
        for index, line in enumerate(lines):
            start_match = START_TABBED_SECTION_REGEX.search(line)
            if start_match:
                block['start_tabs_index'] = index

            tab_content_match = TAB_CONTENT_REGEX.search(line)
            if tab_content_match:
                block.setdefault('tabs', [])
                tab = {'start': index,
                       'tab_name': tab_content_match.group(1)}
                block['tabs'].append(tab)

            end_match = END_TABBED_SECTION_REGEX.search(line)
            if end_match:
                block['end_tabs_index'] = index
                break
        return block

def makeExtension(*args: Any, **kwargs: str) -> TabbedSectionsGenerator:
    return TabbedSectionsGenerator(**kwargs)
