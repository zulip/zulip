from typing import Optional

import lxml
from lxml.html.diff import htmldiff


def highlight_with_class(text: str, klass: str) -> str:
    return f'<span class="{klass}">{text}</span>'

def highlight_html_differences(s1: str, s2: str, msg_id: Optional[int]=None) -> str:
    retval = htmldiff(s1, s2)
    fragment = lxml.html.fromstring(retval)

    for elem in fragment.cssselect('del'):
        elem.tag = 'span'
        elem.set('class', 'highlight_text_deleted')

    for elem in fragment.cssselect('ins'):
        elem.tag = 'span'
        elem.set('class', 'highlight_text_inserted')

    retval = lxml.html.tostring(fragment, encoding="unicode")

    return retval
