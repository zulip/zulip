from __future__ import absolute_import
from __future__ import print_function

import sys
import unittest

try:
    from tools.lib.template_parser import (
        html_tag_tree,
        is_django_block_tag,
        tokenize,
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

    def test_validate_handlebars(self):
        # type: () -> None
        my_html = '''
            {{#with stream}}
                <p>{{stream}}</p>
            {{/with}}
            '''
        validate(text=my_html)

    def test_validate_django(self):
        # type: () -> None
        my_html = '''
            {% include "some_other.html" %}
            {% if foo %}
                <p>bar</p>
            {% endif %}
            '''
        validate(text=my_html)

    def test_tokenize(self):
        # type: () -> None
        tag = '<meta whatever>bla'
        token = tokenize(tag)[0]
        self.assertEqual(token.kind, 'html_special')

        tag = '<a>bla'
        token = tokenize(tag)[0]
        self.assertEqual(token.kind, 'html_start')
        self.assertEqual(token.tag, 'a')

        tag = '<br />bla'
        token = tokenize(tag)[0]
        self.assertEqual(token.kind, 'html_singleton')
        self.assertEqual(token.tag, 'br')

        tag = '</a>bla'
        token = tokenize(tag)[0]
        self.assertEqual(token.kind, 'html_end')
        self.assertEqual(token.tag, 'a')

        tag = '{{#with foo}}bla'
        token = tokenize(tag)[0]
        self.assertEqual(token.kind, 'handlebars_start')
        self.assertEqual(token.tag, 'with')

        tag = '{{/with}}bla'
        token = tokenize(tag)[0]
        self.assertEqual(token.kind, 'handlebars_end')
        self.assertEqual(token.tag, 'with')

        tag = '{% if foo %}bla'
        token = tokenize(tag)[0]
        self.assertEqual(token.kind, 'django_start')
        self.assertEqual(token.tag, 'if')

        tag = '{% endif %}bla'
        token = tokenize(tag)[0]
        self.assertEqual(token.kind, 'django_end')
        self.assertEqual(token.tag, 'if')

    def test_html_tag_tree(self):
        # type: () -> None
        html = '''
        <body><p>Hello world</p></body>
        '''
        tree = html_tag_tree(html)
        self.assertEqual(tree.children[0].children[0].token.s, '<p>')
