#!/usr/bin/env python2.7

"""
Fenced Code Extension for Python Markdown
=========================================

This extension adds Fenced Code Blocks to Python-Markdown.

    >>> import markdown
    >>> text = '''
    ... A paragraph before a fenced code block:
    ...
    ... ~~~
    ... Fenced code block
    ... ~~~
    ... '''
    >>> html = markdown.markdown(text, extensions=['fenced_code'])
    >>> print html
    <p>A paragraph before a fenced code block:</p>
    <pre><code>Fenced code block
    </code></pre>

Works with safe_mode also (we check this because we are using the HtmlStash):

    >>> print markdown.markdown(text, extensions=['fenced_code'], safe_mode='replace')
    <p>A paragraph before a fenced code block:</p>
    <pre><code>Fenced code block
    </code></pre>

Include tilde's in a code block and wrap with blank lines:

    >>> text = '''
    ... ~~~~~~~~
    ...
    ... ~~~~
    ... ~~~~~~~~'''
    >>> print markdown.markdown(text, extensions=['fenced_code'])
    <pre><code>
    ~~~~
    </code></pre>

Language tags:

    >>> text = '''
    ... ~~~~{.python}
    ... # Some python code
    ... ~~~~'''
    >>> print markdown.markdown(text, extensions=['fenced_code'])
    <pre><code class="python"># Some python code
    </code></pre>

Copyright 2007-2008 [Waylan Limberg](http://achinghead.com/).

Project website: <http://packages.python.org/Markdown/extensions/fenced_code_blocks.html>
Contact: markdown@freewisdom.org

License: BSD (see ../docs/LICENSE for details)

Dependencies:
* [Python 2.4+](http://python.org)
* [Markdown 2.0+](http://packages.python.org/Markdown/)
* [Pygments (optional)](http://pygments.org)

"""

import re
import markdown
from zerver.lib.bugdown.codehilite import CodeHilite, CodeHiliteExtension

# Global vars
FENCE_RE = re.compile(r"""
    # ~~~ or ```
    (?P<fence>
        ^(?:~{3,}|`{3,})
    )

    [ ]* # spaces

    (
        \{?\.?
        (?P<lang>
            [a-zA-Z0-9_+-]*
        ) # "py" or "javascript"
        \}?
    ) # language, like ".py" or "{javascript}"
    [ ]* # spaces
    $
    """, re.VERBOSE)


CODE_WRAP = '<pre><code%s>%s</code></pre>'
LANG_TAG = ' class="%s"'

class FencedCodeExtension(markdown.Extension):

    def extendMarkdown(self, md, md_globals):
        """ Add FencedBlockPreprocessor to the Markdown instance. """
        md.registerExtension(self)

        # Newer versions of Python-Markdown (starting at 2.3?) have
        # a normalize_whitespace preprocessor that needs to go first.
        position = ('>normalize_whitespace'
            if 'normalize_whitespace' in md.preprocessors
            else '_begin')

        md.preprocessors.add('fenced_code_block',
                                 FencedBlockPreprocessor(md),
                                 position)


class FencedBlockPreprocessor(markdown.preprocessors.Preprocessor):

    def __init__(self, md):
        markdown.preprocessors.Preprocessor.__init__(self, md)

        self.checked_for_codehilite = False
        self.codehilite_conf = {}

    def run(self, lines):
        """ Match and store Fenced Code Blocks in the HtmlStash. """

        output = []

        class Record(object):
            pass

        processor = self
        handlers = []

        def push(handler):
            handlers.append(handler)

        def pop():
            handlers.pop()

        class OuterHandler(object):
            def __init__(self, output):
                self.output = output

            def handle_line(self, line):
                check_for_new_fence(self.output, line)

            def done(self):
                pop()

        def check_for_new_fence(output, line):
            m = FENCE_RE.match(line)
            if m:
                fence = m.group('fence')
                lang = m.group('lang')
                handler = generic_handler(output, fence, lang)
                push(handler)
            else:
                output.append(line)

        def generic_handler(output, fence, lang):
            if lang in ('quote', 'quoted'):
                return QuoteHandler(output, fence)
            else:
                return CodeHandler(output, fence, lang)

        class QuoteHandler(object):
            def __init__(self, output, fence):
                self.output = output
                self.fence = fence
                self.lines = []

            def handle_line(self, line):
                if line.rstrip() == self.fence:
                    self.done()
                else:
                    check_for_new_fence(self.lines, line)

            def done(self):
                text = '\n'.join(self.lines)
                text = processor.format_quote(text)
                processed_lines = text.split('\n')
                self.output.append('')
                self.output.extend(processed_lines)
                self.output.append('')
                pop()

        class CodeHandler(object):
            def __init__(self, output, fence, lang):
                self.output = output
                self.fence = fence
                self.lang = lang
                self.lines = []

            def handle_line(self, line):
                if line.rstrip() == self.fence:
                    self.done()
                else:
                    self.lines.append(line)

            def done(self):
                text = '\n'.join(self.lines)
                text = processor.format_code(self.lang, text)
                text = processor.placeholder(text)
                processed_lines = text.split('\n')
                self.output.append('')
                self.output.extend(processed_lines)
                self.output.append('')
                pop()

        handler = OuterHandler(output)
        push(handler)

        for line in lines:
            handlers[-1].handle_line(line)

        while handlers:
            handlers[-1].done()

        # This fiddly handling of new lines at the end of our output was done to make
        # existing tests pass.  Bugdown is just kind of funny when it comes to new lines,
        # but we could probably remove this hack.
        if len(output) > 2 and output[-2] != '':
            output.append('')
        return output

    def format_code(self, lang, text):
        langclass = ''
        if lang:
            langclass = LANG_TAG % (lang,)

        # Check for code hilite extension
        if not self.checked_for_codehilite:
            for ext in self.markdown.registeredExtensions:
                if isinstance(ext, CodeHiliteExtension):
                    self.codehilite_conf = ext.config
                    break

            self.checked_for_codehilite = True

        # If config is not empty, then the codehighlite extension
        # is enabled, so we call it to highlite the code
        if self.codehilite_conf:
            highliter = CodeHilite(text,
                    force_linenos=self.codehilite_conf['force_linenos'][0],
                    guess_lang=self.codehilite_conf['guess_lang'][0],
                    css_class=self.codehilite_conf['css_class'][0],
                    style=self.codehilite_conf['pygments_style'][0],
                    lang=(lang or None),
                    noclasses=self.codehilite_conf['noclasses'][0])

            code = highliter.hilite()
        else:
            code = CODE_WRAP % (langclass, self._escape(text))

        return code

    def format_quote(self, text):
        paragraphs = text.split("\n\n")
        quoted_paragraphs = []
        for paragraph in paragraphs:
            lines = paragraph.split("\n")
            quoted_paragraphs.append("\n".join("> " + line for line in lines if line != ''))
        return "\n\n".join(quoted_paragraphs)

    def placeholder(self, code):
        return self.markdown.htmlStash.store(code, safe=True)

    def _escape(self, txt):
        """ basic html escaping """
        txt = txt.replace('&', '&amp;')
        txt = txt.replace('<', '&lt;')
        txt = txt.replace('>', '&gt;')
        txt = txt.replace('"', '&quot;')
        return txt


def makeExtension(configs=None):
    return FencedCodeExtension(configs=configs)


if __name__ == "__main__":
    import doctest
    doctest.testmod()
