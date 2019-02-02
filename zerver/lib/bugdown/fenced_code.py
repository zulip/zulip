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

Removes trailing whitespace from code blocks that cause horizontal scrolling
    >>> import markdown
    >>> text = '''
    ... A paragraph before a fenced code block:
    ...
    ... ~~~
    ... Fenced code block    \t\t\t\t\t\t\t
    ... ~~~
    ... '''
    >>> html = markdown.markdown(text, extensions=['fenced_code'])
    >>> print html
    <p>A paragraph before a fenced code block:</p>
    <pre><code>Fenced code block
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
from django.utils.html import escape
from markdown.extensions.codehilite import CodeHilite, CodeHiliteExtension
from zerver.lib.tex import render_tex
from typing import Any, Dict, Iterable, List, MutableSequence

# Global vars
FENCE_RE = re.compile("""
    # ~~~ or ```
    (?P<fence>
        ^(?:~{3,}|`{3,})
    )

    [ ]* # spaces

    (
        \\{?\\.?
        (?P<lang>
            [a-zA-Z0-9_+-./#]*
        ) # "py" or "javascript"
        \\}?
    ) # language, like ".py" or "{javascript}"
    [ ]* # spaces
    $
    """, re.VERBOSE)


CODE_WRAP = '<pre><code%s>%s\n</code></pre>'
LANG_TAG = ' class="%s"'

class FencedCodeExtension(markdown.Extension):

    def extendMarkdown(self, md: markdown.Markdown, md_globals: Dict[str, Any]) -> None:
        """ Add FencedBlockPreprocessor to the Markdown instance. """
        md.registerExtension(self)
        md.preprocessors.register(FencedBlockPreprocessor(md), 'fenced_code_block', 25)


class BaseHandler:
    def handle_line(self, line: str) -> None:
        raise NotImplementedError()

    def done(self) -> None:
        raise NotImplementedError()

def generic_handler(processor: Any, output: MutableSequence[str], fence: str, lang: str) -> BaseHandler:
    if lang in ('quote', 'quoted'):
        return QuoteHandler(processor, output, fence)
    elif lang in ('math', 'tex', 'latex'):
        return TexHandler(processor, output, fence)
    else:
        return CodeHandler(processor, output, fence, lang)

def check_for_new_fence(processor: Any, output: MutableSequence[str], line: str) -> None:
    m = FENCE_RE.match(line)
    if m:
        fence = m.group('fence')
        lang = m.group('lang')
        handler = generic_handler(processor, output, fence, lang)
        processor.push(handler)
    else:
        output.append(line)

class OuterHandler(BaseHandler):
    def __init__(self, processor: Any, output: MutableSequence[str]) -> None:
        self.output = output
        self.processor = processor

    def handle_line(self, line: str) -> None:
        check_for_new_fence(self.processor, self.output, line)

    def done(self) -> None:
        self.processor.pop()

class CodeHandler(BaseHandler):
    def __init__(self, processor: Any, output: MutableSequence[str], fence: str, lang: str) -> None:
        self.processor = processor
        self.output = output
        self.fence = fence
        self.lang = lang
        self.lines = []  # type: List[str]

    def handle_line(self, line: str) -> None:
        if line.rstrip() == self.fence:
            self.done()
        else:
            self.lines.append(line.rstrip())

    def done(self) -> None:
        text = '\n'.join(self.lines)
        text = self.processor.format_code(self.lang, text)
        text = self.processor.placeholder(text)
        processed_lines = text.split('\n')
        self.output.append('')
        self.output.extend(processed_lines)
        self.output.append('')
        self.processor.pop()

class QuoteHandler(BaseHandler):
    def __init__(self, processor: Any, output: MutableSequence[str], fence: str) -> None:
        self.processor = processor
        self.output = output
        self.fence = fence
        self.lines = []  # type: List[str]

    def handle_line(self, line: str) -> None:
        if line.rstrip() == self.fence:
            self.done()
        else:
            check_for_new_fence(self.processor, self.lines, line)

    def done(self) -> None:
        text = '\n'.join(self.lines)
        text = self.processor.format_quote(text)
        processed_lines = text.split('\n')
        self.output.append('')
        self.output.extend(processed_lines)
        self.output.append('')
        self.processor.pop()

class TexHandler(BaseHandler):
    def __init__(self, processor: Any, output: MutableSequence[str], fence: str) -> None:
        self.processor = processor
        self.output = output
        self.fence = fence
        self.lines = []  # type: List[str]

    def handle_line(self, line: str) -> None:
        if line.rstrip() == self.fence:
            self.done()
        else:
            self.lines.append(line)

    def done(self) -> None:
        text = '\n'.join(self.lines)
        text = self.processor.format_tex(text)
        text = self.processor.placeholder(text)
        processed_lines = text.split('\n')
        self.output.append('')
        self.output.extend(processed_lines)
        self.output.append('')
        self.processor.pop()


class FencedBlockPreprocessor(markdown.preprocessors.Preprocessor):
    def __init__(self, md: markdown.Markdown) -> None:
        markdown.preprocessors.Preprocessor.__init__(self, md)

        self.checked_for_codehilite = False
        self.codehilite_conf = {}  # type: Dict[str, List[Any]]

    def push(self, handler: BaseHandler) -> None:
        self.handlers.append(handler)

    def pop(self) -> None:
        self.handlers.pop()

    def run(self, lines: Iterable[str]) -> List[str]:
        """ Match and store Fenced Code Blocks in the HtmlStash. """

        output = []  # type: List[str]

        processor = self
        self.handlers = []  # type: List[BaseHandler]

        handler = OuterHandler(processor, output)
        self.push(handler)

        for line in lines:
            self.handlers[-1].handle_line(line)

        while self.handlers:
            self.handlers[-1].done()

        # This fiddly handling of new lines at the end of our output was done to make
        # existing tests pass.  Bugdown is just kind of funny when it comes to new lines,
        # but we could probably remove this hack.
        if len(output) > 2 and output[-2] != '':
            output.append('')
        return output

    def format_code(self, lang: str, text: str) -> str:
        if lang:
            langclass = LANG_TAG % (lang,)
        else:
            langclass = ''

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
                                   linenums=self.codehilite_conf['linenums'][0],
                                   guess_lang=self.codehilite_conf['guess_lang'][0],
                                   css_class=self.codehilite_conf['css_class'][0],
                                   style=self.codehilite_conf['pygments_style'][0],
                                   use_pygments=self.codehilite_conf['use_pygments'][0],
                                   lang=(lang or None),
                                   noclasses=self.codehilite_conf['noclasses'][0])

            code = highliter.hilite()
        else:
            code = CODE_WRAP % (langclass, self._escape(text))

        return code

    def format_quote(self, text: str) -> str:
        paragraphs = text.split("\n\n")
        quoted_paragraphs = []
        for paragraph in paragraphs:
            lines = paragraph.split("\n")
            quoted_paragraphs.append("\n".join("> " + line for line in lines if line != ''))
        return "\n\n".join(quoted_paragraphs)

    def format_tex(self, text: str) -> str:
        paragraphs = text.split("\n\n")
        tex_paragraphs = []
        for paragraph in paragraphs:
            html = render_tex(paragraph, is_inline=False)
            if html is not None:
                tex_paragraphs.append(html)
            else:
                tex_paragraphs.append('<span class="tex-error">' +
                                      escape(paragraph) + '</span>')
        return "\n\n".join(tex_paragraphs)

    def placeholder(self, code: str) -> str:
        return self.markdown.htmlStash.store(code)

    def _escape(self, txt: str) -> str:
        """ basic html escaping """
        txt = txt.replace('&', '&amp;')
        txt = txt.replace('<', '&lt;')
        txt = txt.replace('>', '&gt;')
        txt = txt.replace('"', '&quot;')
        return txt


def makeExtension(*args: Any, **kwargs: None) -> FencedCodeExtension:
    return FencedCodeExtension(*args, **kwargs)

if __name__ == "__main__":
    import doctest
    doctest.testmod()
