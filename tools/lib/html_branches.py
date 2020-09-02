import re
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Set

from .template_parser import FormattedException, Token, tokenize


class HtmlBranchesException(Exception):
    # TODO: Have callers pass in line numbers.
    pass


class HtmlTreeBranch:
    """
    For <p><div id='yo'>bla<span class='bar'></span></div></p>, store a
    representation of the tags all the way down to the leaf, which would
    conceptually be something like "p div(#yo) span(.bar)".
    """

    def __init__(self, tags: List['TagInfo'], fn: Optional[str]) -> None:
        self.tags = tags
        self.fn = fn
        self.line = tags[-1].token.line

        self.words: Set[str] = set()
        for tag in tags:
            for word in tag.words:
                self.words.add(word)

    def staircase_text(self) -> str:
        """
        produces representation of a node in staircase-like format:

            html
                body.main-section
                    p#intro

        """
        res = '\n'
        indent = ' ' * 4
        for t in self.tags:
            res += indent + t.text() + '\n'
            indent += ' ' * 4
        return res

    def text(self) -> str:
        """
        produces one-line representation of branch:

        html body.main-section p#intro
        """
        return ' '.join(t.text() for t in self.tags)


class Node:
    def __init__(self, token: Optional[Token], parent: "Optional[Node]") -> None:
        # FIXME parent parameter is not used!
        self.token = token
        self.children: List[Node] = []
        self.parent: Optional[Node] = None


class TagInfo:
    def __init__(self, tag: str, classes: List[str], ids: List[str], token: Token) -> None:
        self.tag = tag
        self.classes = classes
        self.ids = ids
        self.token = token
        self.words = [
            self.tag,
            *('.' + s for s in classes),
            *('#' + s for s in ids),
        ]

    def text(self) -> str:
        s = self.tag
        if self.classes:
            s += '.' + '.'.join(self.classes)
        if self.ids:
            s += '#' + '#'.join(self.ids)
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
    s = ''

    for ch in element:
        if ch == '{':
            outside_braces = False
        if ch == '}':
            outside_braces = True
        if ch == ' ' and outside_braces:
            if not s == '':
                lst.append(s)
            s = ''
        else:
            s += ch
    if not s == '':
        lst.append(s)

    return lst


def html_branches(text: str, fn: Optional[str] = None) -> List[HtmlTreeBranch]:
    tree = html_tag_tree(text, fn)
    branches: List[HtmlTreeBranch] = []

    def walk(node: Node, tag_info_list: Sequence[TagInfo] = []) -> None:
        assert node.token is not None
        info = get_tag_info(node.token)
        tag_info_list = [*tag_info_list, info]

        if node.children:
            for child in node.children:
                walk(node=child, tag_info_list=tag_info_list)
        else:
            tree_branch = HtmlTreeBranch(tags=tag_info_list, fn=fn)
            branches.append(tree_branch)

    for node in tree.children:
        walk(node, [])

    return branches


def html_tag_tree(text: str, fn: Optional[str]=None) -> Node:
    tokens = tokenize(text)
    top_level = Node(token=None, parent=None)
    stack = [top_level]

    for token in tokens:
        # Add tokens to the Node tree first (conditionally).
        if token.kind in ('html_start', 'html_singleton'):
            parent = stack[-1]
            node = Node(token=token, parent=parent)
            parent.children.append(node)

        # Then update the stack to have the next node that
        # we will be appending to at the top.
        if token.kind == 'html_start':
            stack.append(node)
        elif token.kind == 'html_end':
            stack.pop()

    return top_level


def build_id_dict(templates: List[str]) -> (Dict[str, List[str]]):
    template_id_dict: (Dict[str, List[str]]) = defaultdict(list)

    for fn in templates:
        with open(fn) as f:
            text = f.read()

        try:
            list_tags = tokenize(text)
        except FormattedException as e:
            raise Exception(f'''
                fn: {fn}
                {e}''')

        for tag in list_tags:
            info = get_tag_info(tag)

            for ids in info.ids:
                template_id_dict[ids].append("Line " + str(info.token.line) + ":" + fn)

    return template_id_dict
