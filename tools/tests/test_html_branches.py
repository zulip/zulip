import os
import unittest

import tools.lib.template_parser
from tools.lib.html_branches import (
    Node,
    build_id_dict,
    get_tag_info,
    html_branches,
    html_tag_tree,
    split_for_id_and_class,
)

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_template_data")


class TestHtmlBranches(unittest.TestCase):
    def test_get_tag_info(self) -> None:
        html = """
            <p id="test" class="test1 test2">foo</p>
        """

        start_tag, end_tag = tools.lib.template_parser.tokenize(html)

        start_tag_info = get_tag_info(start_tag)
        end_tag_info = get_tag_info(end_tag)

        self.assertEqual(start_tag_info.text(), "p.test1.test2#test")
        self.assertEqual(end_tag_info.text(), "p")

    def test_html_tag_tree(self) -> None:
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
                <p>Hello<br>world!</p>
                <p>Goodbye<!-- test -->world!</p>
            </body>
            </html>
            <!-- test -->
        """

        tree = html_tag_tree(html)

        def serialize(node: Node) -> object:
            return (
                node.token and (node.token.kind, node.token.tag),
                [serialize(child) for child in node.children],
            )

        expected = (
            None,
            [
                (
                    ("html_start", "html"),
                    [
                        (
                            ("html_start", "head"),
                            [
                                (("html_start", "title"), []),
                                (("html_singleton", "meta"), []),
                                (("html_singleton", "link"), []),
                            ],
                        ),
                        (
                            ("html_start", "body"),
                            [
                                (
                                    ("html_start", "p"),
                                    [(("html_start", "br"), []), (("html_start", "p"), [])],
                                )
                            ],
                        ),
                    ],
                )
            ],
        )
        self.assertEqual(serialize(tree), expected)

    def test_html_branches(self) -> None:
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
                <p>Hello<br>world!</p>
                <p>Goodbye<!-- test -->world!</p>
            </body>
            </html>
            <!-- test -->
        """

        branches = html_branches(html)
        self.assertEqual(
            [(branch.text(), branch.staircase_text()) for branch in branches],
            [
                ("html head title", "\n    html\n        head\n            title\n"),
                ("html head meta", "\n    html\n        head\n            meta\n"),
                ("html head link", "\n    html\n        head\n            link\n"),
                ("html body p br", "\n    html\n        body\n            p\n                br\n"),
                ("html body p p", "\n    html\n        body\n            p\n                p\n"),
            ],
        )

    def test_build_id_dict(self) -> None:
        templates = ["test_template1.html", "test_template2.html"]
        templates = [os.path.join(TEST_TEMPLATES_DIR, fn) for fn in templates]

        template_id_dict = build_id_dict(templates)

        self.assertEqual(
            set(template_id_dict.keys()), {"below_navbar", "hello_{{ message }}", "intro"}
        )
        self.assertEqual(
            template_id_dict["hello_{{ message }}"],
            [
                f"Line 12:{ZULIP_PATH}/tools/tests/test_template_data/test_template1.html",
                f"Line 12:{ZULIP_PATH}/tools/tests/test_template_data/test_template2.html",
            ],
        )
        self.assertEqual(
            template_id_dict["intro"],
            [
                f"Line 10:{ZULIP_PATH}/tools/tests/test_template_data/test_template1.html",
                f"Line 11:{ZULIP_PATH}/tools/tests/test_template_data/test_template1.html",
                f"Line 11:{ZULIP_PATH}/tools/tests/test_template_data/test_template2.html",
            ],
        )
        self.assertEqual(
            template_id_dict["below_navbar"],
            [f"Line 10:{ZULIP_PATH}/tools/tests/test_template_data/test_template2.html"],
        )

    def test_split_for_id_and_class(self) -> None:
        id1 = "{{ red|blue }}"
        id2 = "search_box_{{ page }}"

        class1 = "chat_box message"
        class2 = "stream_{{ topic }}"
        class3 = "foo {{ a|b|c }} bar"

        self.assertEqual(split_for_id_and_class(id1), ["{{ red|blue }}"])
        self.assertEqual(split_for_id_and_class(id2), ["search_box_{{ page }}"])

        self.assertEqual(split_for_id_and_class(class1), ["chat_box", "message"])
        self.assertEqual(split_for_id_and_class(class2), ["stream_{{ topic }}"])
        self.assertEqual(split_for_id_and_class(class3), ["foo", "{{ a|b|c }}", "bar"])
