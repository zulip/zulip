from __future__ import absolute_import
from __future__ import print_function

import unittest

import tools.lib.template_parser

from tools.lib.html_branches import (
    get_tag_info,
    html_branches,
    html_tag_tree,
)


class TestHtmlBranches(unittest.TestCase):

    def test_get_tag_info(self):
        # type: () -> None
        html = """
            <p id="test" class="test1 test2">foo</p>
        """

        start_tag, end_tag = tools.lib.template_parser.tokenize(html)

        start_tag_info = get_tag_info(start_tag)
        end_tag_info = get_tag_info(end_tag)

        self.assertEqual(start_tag_info.text(), 'p.test1.test2#test')
        self.assertEqual(end_tag_info.text(), 'p')

    def test_html_tag_tree(self):
        # type: () -> None
        html = """
            <!-- test -->
            <!DOCTYPE html>
            <html>
            <!-- test -->
            <head>
                <title>Test</title>
                <meta charset="utf-8" />
                <link rel="stylesheet" href="style.css" />
            </head>
            <body>
                <p>Hello<br />world!</p>
                <p>Goodbye<!-- test -->world!</p>
            </body>
            </html>
            <!-- test -->
        """

        tree = html_tag_tree(html)

        self.assertEqual(tree.children[0].token.kind, 'html_start')
        self.assertEqual(tree.children[0].token.tag, 'html')

        self.assertEqual(tree.children[0].children[0].token.kind, 'html_start')
        self.assertEqual(tree.children[0].children[0].token.tag, 'head')

        self.assertEqual(tree.children[0].children[0].children[0].token.kind, 'html_start')
        self.assertEqual(tree.children[0].children[0].children[0].token.tag, 'title')

        self.assertEqual(tree.children[0].children[1].token.kind, 'html_start')
        self.assertEqual(tree.children[0].children[1].token.tag, 'body')

        self.assertEqual(tree.children[0].children[1].children[0].token.kind, 'html_start')
        self.assertEqual(tree.children[0].children[1].children[0].token.tag, 'p')

        self.assertEqual(tree.children[0].children[1].children[0].children[0].token.kind, 'html_singleton')
        self.assertEqual(tree.children[0].children[1].children[0].children[0].token.tag, 'br')

        self.assertEqual(tree.children[0].children[1].children[1].token.kind, 'html_start')
        self.assertEqual(tree.children[0].children[1].children[1].token.tag, 'p')

    def test_html_branches(self):
        # type: () -> None
        html = """
            <!-- test -->
            <!DOCTYPE html>
            <html>
            <!-- test -->
            <head>
                <title>Test</title>
                <meta charset="utf-8" />
                <link rel="stylesheet" href="style.css" />
            </head>
            <body>
                <p>Hello<br />world!</p>
                <p>Goodbye<!-- test -->world!</p>
            </body>
            </html>
            <!-- test -->
        """

        branches = html_branches(html)

        self.assertEqual(branches[0].text(), 'html head title')
        self.assertEqual(branches[1].text(), 'html body p br')
        self.assertEqual(branches[2].text(), 'html body p')

        self.assertEqual(branches[0].staircase_text(), '\n    html\n        head\n            title\n')
        self.assertEqual(branches[1].staircase_text(), '\n    html\n        body\n            p\n                br\n')
        self.assertEqual(branches[2].staircase_text(), '\n    html\n        body\n            p\n')
