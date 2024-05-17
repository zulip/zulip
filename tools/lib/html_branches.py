import re
from collections import defaultdict
from typing import Dict, List

from .template_parser import FormattedError, Token, tokenize


class TagInfo:
    def __init__(self, tag: str, classes: List[str], ids: List[str], token: Token) -> None:
        self.tag = tag
        self.classes = classes
        self.ids = ids
        self.token = token
        self.words = [
            self.tag,
            *("." + s for s in classes),
            *("#" + s for s in ids),
        ]

    def text(self) -> str:
        s = self.tag
        if self.classes:
            s += "." + ".".join(self.classes)
        if self.ids:
            s += "#" + "#".join(self.ids)
        return s


def get_tag_info(token: Token) -> TagInfo:
    s = token.s
    tag = token.tag
    classes: List[str] = []
    ids: List[str] = []

    searches = [
        (classes, ' class="(.*?)"'),
        (classes, " class='(.*?)'"),
        (ids, ' id="(.*?)"'),
        (ids, " id='(.*?)'"),
    ]

    for lst, regex in searches:
        m = re.search(regex, s)
        if m:
            for g in m.groups():
                lst += split_for_id_and_class(g)

    return TagInfo(tag=tag, classes=classes, ids=ids, token=token)


def split_for_id_and_class(element: str) -> List[str]:
    # Here we split a given string which is expected to contain id or class
    # attributes from HTML tags. This also takes care of template variables
    # in string during splitting process. For eg. 'red black {{ a|b|c }}'
    # is split as ['red', 'black', '{{ a|b|c }}']
    outside_braces: bool = True
    lst = []
    s = ""

    for ch in element:
        if ch == "{":
            outside_braces = False
        if ch == "}":
            outside_braces = True
        if ch == " " and outside_braces:
            if s != "":
                lst.append(s)
            s = ""
        else:
            s += ch
    if s != "":
        lst.append(s)

    return lst


def build_id_dict(templates: List[str]) -> Dict[str, List[str]]:
    template_id_dict: Dict[str, List[str]] = defaultdict(list)

    for fn in templates:
        with open(fn) as f:
            text = f.read()

        try:
            list_tags = tokenize(text)
        except FormattedError as e:
            raise Exception(
                f"""
                fn: {fn}
                {e}"""
            )

        for tag in list_tags:
            info = get_tag_info(tag)

            for ids in info.ids:
                template_id_dict[ids].append("Line " + str(info.token.line) + ":" + fn)

    return template_id_dict
