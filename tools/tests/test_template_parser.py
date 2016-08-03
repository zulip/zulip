from __future__ import absolute_import
from __future__ import print_function

import sys
import unittest

try:
    from tools.lib.template_parser import (
        is_django_block_tag,
        validate,
    )
except ImportError:
    print('ERROR!!! You need to run this via tools/test-tools.')
    sys.exit(1)

class ParserTest(unittest.TestCase):
    def test_is_django_block_tag(self):
        # type: () -> None
        self.assertTrue(is_django_block_tag('block'))
        self.assertFalse(is_django_block_tag('not a django tag'))

    def test_validate_vanilla_html(self):
        # type: () -> None
        '''
        Verify that validate() does not raise errors for
        well-formed HTML.
        '''
        my_html = '''
            <table>
                <tr>
                <td>foo</td>
                </tr>
            </table>'''
        validate(text=my_html)
