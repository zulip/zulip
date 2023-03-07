from typing import Optional

import lxml.html
from lxml.html.diff import htmldiff


def highlight_html_differences(s1: str, s2: str, msg_id: Optional[int] = None) -> str:
    retval = htmldiff(s1, s2)
    fragment = lxml.html.fragment_fromstring(retval, create_parent=True)

    for elem in fragment.cssselect("del"):
        elem.tag = "span"
        elem.set("class", "highlight_text_deleted")

    for elem in fragment.cssselect("ins"):
        elem.tag = "span"
        elem.set("class", "highlight_text_inserted")

    retval = lxml.html.tostring(fragment, encoding="unicode")

    return retval
