from __future__ import absolute_import
from __future__ import print_function

from typing import cast, Any

import sys
import unittest

try:
    from tools.lib.css_parser import (
        CssParserException,
        CssSection,
        parse,
    )
except ImportError:
    print('ERROR!!! You need to run this via tools/test-tools.')
    sys.exit(1)

class ParserTestHappyPath(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        # This method should be removed when we migrate to version 3 of Python
        import six
        if six.PY2:
            self.assertRaisesRegex = self.assertRaisesRegexp  # type: ignore
        super(ParserTestHappyPath, self).__init__(*args, **kwargs)

    def test_basic_parse(self):
        # type: () -> None
        my_selector = 'li.foo'
        my_block = '''{
                color: red;
            }'''
        my_css = my_selector + ' ' + my_block
        res = parse(my_css)
        self.assertEqual(res.text(), my_css)
        section = cast(CssSection, res.sections[0])
        block = section.declaration_block
        self.assertEqual(block.text().strip(), my_block)
        declaration = block.declarations[0]
        self.assertEqual(declaration.css_property, 'color')
        self.assertEqual(declaration.css_value.text().strip(), 'red')

    def test_same_line_comment(self):
        # type: () -> None
        my_css = '''
            li.hide {
                display: none; /* comment here */
                /* Not to be confused
                   with this comment */
                color: green;
            }'''
        res = parse(my_css)
        section = cast(CssSection, res.sections[0])
        block = section.declaration_block
        declaration = block.declarations[0]
        self.assertIn('/* comment here */', declaration.text())

    def test_no_semicolon(self):
        # type: () -> None
        my_css = '''
            p { color: red }
        '''

        reformatted_css = '''
            p { color: red;}
        '''

        res = parse(my_css)

        self.assertEqual(res.text(), reformatted_css)

        section = cast(CssSection, res.sections[0])

        self.assertFalse(section.declaration_block.declarations[0].semicolon)

    def test_empty_block(self):
        # type: () -> None
        my_css = '''
            div {
            }'''
        error = 'Empty declaration'
        with self.assertRaisesRegex(CssParserException, error):
            parse(my_css)

    def test_multi_line_selector(self):
        # type: () -> None
        my_css = '''
            h1,
            h2,
            h3 {
                top: 0
            }'''
        res = parse(my_css)
        section = res.sections[0]
        selectors = section.selector_list.selectors
        self.assertEqual(len(selectors), 3)

    def test_comment_at_end(self):
        # type: () -> None
        '''
        This test verifies the current behavior, which is to
        attach comments to the preceding rule, but we should
        probably change it so the comments gets attached to
        the next block, if possible.
        '''
        my_css = '''
            p {
                color: black;
            }

            /* comment at the end of the text */
            '''
        res = parse(my_css)
        self.assertEqual(len(res.sections), 1)
        section = res.sections[0]
        self.assertIn('comment at the end', section.post_fluff)

    def test_media_block(self):
        # type: () -> None
        my_css = '''
            @media (max-width: 300px) {
                h5 {
                    margin: 0;
                }
            }'''
        res = parse(my_css)
        self.assertEqual(len(res.sections), 1)
        self.assertEqual(res.text(), my_css)

class ParserTestSadPath(unittest.TestCase):
    '''
    Use this class for tests that verify the parser will
    appropriately choke on malformed CSS.

    We prevent some things that are technically legal
    in CSS, like having comments in the middle of list
    of selectors.  Some of this is just for expediency;
    some of this is to enforce consistent formatting.
    '''
    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        # This method should be removed when we migrate to version 3 of Python
        import six
        if six.PY2:
            self.assertRaisesRegex = self.assertRaisesRegexp  # type: ignore
        super(ParserTestSadPath, self).__init__(*args, **kwargs)

    def _assert_error(self, my_css, error):
        # type: (str, str) -> None
        with self.assertRaisesRegex(CssParserException, error):
            parse(my_css)

    def test_unexpected_end_brace(self):
        # type: () -> None
        my_css = '''
            @media (max-width: 975px) {
                body {
                    color: red;
                }
            }} /* whoops */'''
        error = 'unexpected }'
        self._assert_error(my_css, error)

    def test_empty_section(self):
        # type: () -> None
        my_css = '''

            /* nothing to see here, move along */
            '''
        error = 'unexpected empty section'
        self._assert_error(my_css, error)

    def test_missing_colon(self):
        # type: () -> None
        my_css = '''
            .hide
            {
                display none /* no colon here */
            }'''
        error = 'We expect a colon here'
        self._assert_error(my_css, error)

    def test_unclosed_comment(self):
        # type: () -> None
        my_css = ''' /* comment with no end'''
        error = 'unclosed comment'
        self._assert_error(my_css, error)

    def test_missing_selectors(self):
        # type: () -> None
        my_css = '''
            /* no selectors here */
            {
                bottom: 0
            }'''
        error = 'Missing selector'
        self._assert_error(my_css, error)

    def test_missing_value(self):
        # type: () -> None
        my_css = '''
            h1
            {
                bottom:
            }'''
        error = 'Missing value'
        self._assert_error(my_css, error)

    def test_disallow_comments_in_selectors(self):
        # type: () -> None
        my_css = '''
            h1,
            h2, /* comment here not allowed by Zulip */
            h3 {
                top: 0
            }'''
        error = 'Comments in selector section are not allowed'
        self._assert_error(my_css, error)
