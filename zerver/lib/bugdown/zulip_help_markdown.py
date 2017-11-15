from __future__ import absolute_import
import re
import os
import markdown
import six
from typing import Any, Dict, Iterable, List, MutableSequence, Optional, Tuple, Union, Text
from typing.re import Match
from xml.etree.cElementTree import Element
from zerver.lib.cache import cache

class HelpMarkdownExtension(markdown.Extension):

    def extendMarkdown(self, md, md_globals):
        # type: (markdown.Markdown, Dict[str, Any]) -> None
        """ Add HelpMarkdownExtension to the Markdown instance. """
        md.registerExtension(self)
        md.inlinePatterns.add('icon',
                              Icon(r'!icon\((?P<icon_name>.*?)\)'),
                              '>backtick')

@cache
def get_fa_icons():
    # type: () -> List[str]
    allowed_fa_icons = []  # type: List[str]
    ZERVER_LIB_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ZULIP_PATH = os.path.dirname(os.path.dirname(ZERVER_LIB_PATH))
    FA_CSS_FILE = os.path.join(ZULIP_PATH, 'static', 'third', 'thirdparty-fonts.css')
    with open(FA_CSS_FILE) as f:
        content = f.read()
        icons = re.findall('fa-(\S*):before', content)
        allowed_fa_icons = allowed_fa_icons + icons
    return allowed_fa_icons

class Icon(markdown.inlinepatterns.Pattern):
    def handleMatch(self, match):
        # type: (Match[Text]) -> Optional[Element]
        allowed_fa_icons = get_fa_icons()
        icon_data = match.group('icon_name')
        icon_data = icon_data.strip().lower().split(',')
        icon_name = icon_data[0].strip()
        if len(icon_data) > 1:
            icon_param = icon_data[1].strip()
        else:
            icon_param = ''
        if icon_name in allowed_fa_icons:
            if icon_param == '':
                wrap_icon = markdown.util.etree.Element('span')
                wrap_icon.set('aria-hidden', 'true')
                wrap_icon.text = u'('
                icon = markdown.util.etree.SubElement(wrap_icon, 'i')
                icon.set('class', 'fa fa-%s' % (icon_name))
                icon.tail = u')'
                return wrap_icon
            elif icon_param == 'hidden' or icon_param == 'no-bracket':
                icon = markdown.util.etree.Element('i')
                icon.set('class', 'fa fa-%s' % (icon_name))
                if icon_param == 'hidden':
                    icon.set('aria-hidden', 'true')
                return icon
        return None

def makeExtension(*args, **kwargs):
    # type: (*Any, **Union[bool, None, Text]) -> HelpMarkdownExtension
    return HelpMarkdownExtension(*args, **kwargs)
