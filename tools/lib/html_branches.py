from __future__ import absolute_import
from __future__ import print_function

from typing import Optional

import re

from .template_parser import (
    tokenize,
    Token,
)


class HtmlBranchesException(Exception):
    # TODO: Have callers pass in line numbers.
    pass


class HtmlTreeBranch(object):
    """
    For <p><div id='yo'>bla<span class='bar'></span></div></p>, store a
    representation of the tags all the way down to the leaf, which would
    conceptually be something like "p div(#yo) span(.bar)".
    """

    def __init__(self, tags, fn):
        # type: (List[TagInfo], str) -> None
        self.tags = tags
        self.fn = fn
        self.line = tags[-1].token.line

        self.words = set()  # type: Set[str]
        for tag in tags:
            for word in tag.words:
                self.words.add(word)

    def staircase_text(self):
        # type: () -> str
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

    def text(self):
        # type: () -> str
        """
        produces one-line representation of branch:

        html body.main-section p#intro
        """
        return ' '.join(t.text() for t in self.tags)


class Node(object):
    def __init__(self, token, parent):
        # type: (Token, Node) -> None
        self.token = token
        self.children = []  # type: List[Node]
        self.parent = None  # type: Optional[Node]


class TagInfo(object):
    def __init__(self, tag, classes, ids, token):
        # type: (str, List[str], List[str], Token) -> None
        self.tag = tag
        self.classes = classes
        self.ids = ids
        self.token = token
        self.words = \
            [self.tag] + \
            ['.' + s for s in classes] + \
            ['#' + s for s in ids]

    def text(self):
        # type: () -> str
        s = self.tag
        if self.classes:
            s += '.' + '.'.join(self.classes)
        if self.ids:
            s += '#' + '#'.join(self.ids)
        return s


def get_tag_info(token):
    # type: (Token) -> TagInfo
    s = token.s
    tag = token.tag
    classes = []  # type: List[str]
    ids = []  # type: List[str]

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
                lst += g.split()

    return TagInfo(tag=tag, classes=classes, ids=ids, token=token)


def html_branches(text, fn=None):
    # type: (str, str) -> List[HtmlTreeBranch]

    tree = html_tag_tree(text)
    branches = []  # type: List[HtmlTreeBranch]

    def walk(node, tag_info_list=None):
        # type: (Node, Optional[List[TagInfo]]) -> Node

        info = get_tag_info(node.token)
        if tag_info_list is None:
            tag_info_list = [info]
        else:
            tag_info_list = tag_info_list[:] + [info]

        if node.children:
            for child in node.children:
                walk(node=child, tag_info_list=tag_info_list)
        else:
            tree_branch = HtmlTreeBranch(tags=tag_info_list, fn=fn)
            branches.append(tree_branch)

    for node in tree.children:
        walk(node, None)

    return branches


def html_tag_tree(text):
    # type: (str) -> Node
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
