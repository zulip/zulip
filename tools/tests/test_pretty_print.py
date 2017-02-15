from __future__ import absolute_import
from __future__ import print_function

import unittest

from tools.lib.pretty_print import pretty_print_html

# Note that GOOD_HTML isn't necessarily beautiful HTML.  Apart
# from adjusting indentation, we mostly leave things alone to
# respect whatever line-wrapping styles were in place before.

BAD_HTML = """
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
      <div><p>Hello<br />world!</p></div>
        <p>Goodbye<!-- test -->world!</p>
        <table>
           <tr>
                       <td>5</td>
           </tr>
        </table>
    <pre>
            print 'hello world'
    </pre>
         <div class = "foo"
              id = "bar"
              role = "whatever">{{ bla }}</div>
    </body>
</html>
<!-- test -->
"""

GOOD_HTML = """
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
        <div><p>Hello<br />world!</p></div>
        <p>Goodbye<!-- test -->world!</p>
        <table>
            <tr>
                <td>5</td>
            </tr>
        </table>
        <pre>
                print 'hello world'
        </pre>
        <div class = "foo"
            id = "bar"
             role = "whatever">{{ bla }}</div>
    </body>
</html>
<!-- test -->
"""

BAD_HTML1 = """
<html>
  <body>
    foobarfoobarfoo<b>bar</b>
  </body>
</html>
"""

GOOD_HTML1 = """
<html>
    <body>
        foobarfoobarfoo<b>bar</b>
    </body>
</html>
"""

BAD_HTML2 = """
<html>
  <body>
    {{# foobar area}}
    foobarfoobarfoo<b>bar</b>
    {{/ foobar area}}
  </body>
</html>
"""

GOOD_HTML2 = """
<html>
    <body>
        {{# foobar area}}
        foobarfoobarfoo<b>bar</b>
        {{/ foobar area}}
    </body>
</html>
"""

BAD_HTML3 = """
<html>
  <body>
    {{# foobar area}}
    foobarfoobar<blockquote>
    <p>
        FOOBAR
    </p>
                </blockquote>
    {{/ foobar area}}
  </body>
</html>
"""

GOOD_HTML3 = """
<html>
    <body>
        {{# foobar area}}
        foobarfoobar<blockquote>
                        <p>
                            FOOBAR
                        </p>
                    </blockquote>
        {{/ foobar area}}
    </body>
</html>
"""

BAD_HTML4 = """
<div>
  foo
  <p>hello</p>
  bar
</div>
"""

GOOD_HTML4 = """
<div>
    foo
    <p>hello</p>
    bar
</div>
"""

BAD_HTML5 = """
<div>
  foo
  {{#if foobar}}
  hello
  {{else}}
  bye
  {{/if}}
  bar
</div>
"""

GOOD_HTML5 = """
<div>
    foo
    {{#if foobar}}
    hello
    {{else}}
    bye
    {{/if}}
    bar
</div>
"""

BAD_HTML6 = """
<div>
  <p> <strong> <span class = "whatever">foobar </span> </strong></p>
</div>
"""

GOOD_HTML6 = """
<div>
    <p> <strong> <span class = "whatever">foobar </span> </strong></p>
</div>
"""
class TestPrettyPrinter(unittest.TestCase):
    def compare(self, a, b):
        # type: (str, str) -> None
        self.assertEqual(a.split('\n'), b.split('\n'))

    def test_pretty_print(self):
        # type: () -> None
        self.compare(pretty_print_html(GOOD_HTML), GOOD_HTML)
        self.compare(pretty_print_html(BAD_HTML), GOOD_HTML)
        self.compare(pretty_print_html(BAD_HTML1), GOOD_HTML1)
        self.compare(pretty_print_html(BAD_HTML2), GOOD_HTML2)
        self.compare(pretty_print_html(BAD_HTML3), GOOD_HTML3)
        self.compare(pretty_print_html(BAD_HTML4), GOOD_HTML4)
        self.compare(pretty_print_html(BAD_HTML5), GOOD_HTML5)
        self.compare(pretty_print_html(BAD_HTML6), GOOD_HTML6)
