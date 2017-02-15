from __future__ import absolute_import
from __future__ import print_function

import unittest

from tools.lib.pretty_print import pretty_print_html

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

# Note that GOOD_HTML isn't necessarily beautiful HTML.  Apart
# from adjusting indentation, we mostly leave things alone to
# respect whatever line-wrapping styles were in place before.
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

class TestPrettyPrinter(unittest.TestCase):
    def compare(self, a, b):
        # type: (str, str) -> None
        self.assertEqual(a.split('\n'), b.split('\n'))

    def test_pretty_print(self):
        # type: () -> None
        self.compare(pretty_print_html(BAD_HTML), GOOD_HTML)

