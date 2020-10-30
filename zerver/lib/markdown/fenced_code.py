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
from typing import Any, Dict, Iterable, List, Mapping, MutableSequence, Optional

import lxml.html
import markdown
from django.utils.html import escape
from markdown.extensions.codehilite import CodeHilite, CodeHiliteExtension
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

from zerver.lib.exceptions import MarkdownRenderingException
from zerver.lib.tex import render_tex

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
    (
        \\{?\\.?
        (?P<header>
            [^~`]*
        )
        \\}?
    ) # header for features that use fenced block header syntax (like spoilers)
    $
    """, re.VERBOSE)


CODE_WRAP = '<pre><code{}>{}\n</code></pre>'
LANG_TAG = ' class="{}"'

def validate_curl_content(lines: List[str]) -> None:
    error_msg = """
Missing required -X argument in curl command:

{command}
""".strip()

    for line in lines:
        regex = r'curl [-](sS)?X "?(GET|DELETE|PATCH|POST)"?'
        if line.startswith('curl'):
            if re.search(regex, line) is None:
                raise MarkdownRenderingException(error_msg.format(command=line.strip()))


CODE_VALIDATORS = {
    'curl': validate_curl_content,
}

class FencedCodeExtension(markdown.Extension):
    def __init__(self, config: Mapping[str, Any] = {}) -> None:
        self.config = {
            'run_content_validators': [
                config.get('run_content_validators', False),
                'Boolean specifying whether to run content validation code in CodeHandler',
            ],
        }

        for key, value in config.items():
            self.setConfig(key, value)

    def extendMarkdown(self, md: markdown.Markdown) -> None:
        """ Add FencedBlockPreprocessor to the Markdown instance. """
        md.registerExtension(self)
        processor = FencedBlockPreprocessor(
            md, run_content_validators=self.config['run_content_validators'][0])
        md.preprocessors.register(processor, 'fenced_code_block', 25)


class BaseHandler:
    def handle_line(self, line: str) -> None:
        raise NotImplementedError()

    def done(self) -> None:
        raise NotImplementedError()

def generic_handler(processor: Any, output: MutableSequence[str],
                    fence: str, lang: str, header: str,
                    run_content_validators: bool=False,
                    default_language: Optional[str]=None) -> BaseHandler:
    lang = lang.lower()
    if lang in ('quote', 'quoted'):
        return QuoteHandler(processor, output, fence, default_language)
    elif lang == 'math':
        return TexHandler(processor, output, fence)
    elif lang == 'spoiler':
        return SpoilerHandler(processor, output, fence, header)
    else:
        return CodeHandler(processor, output, fence, lang, run_content_validators)

def check_for_new_fence(processor: Any, output: MutableSequence[str], line: str,
                        run_content_validators: bool=False,
                        default_language: Optional[str]=None) -> None:
    m = FENCE_RE.match(line)
    if m:
        fence = m.group('fence')
        lang = m.group('lang')
        header = m.group('header')
        if not lang and default_language:
            lang = default_language
        handler = generic_handler(processor, output, fence, lang, header,
                                  run_content_validators, default_language)
        processor.push(handler)
    else:
        output.append(line)

class OuterHandler(BaseHandler):
    def __init__(self, processor: Any, output: MutableSequence[str],
                 run_content_validators: bool=False,
                 default_language: Optional[str]=None) -> None:
        self.output = output
        self.processor = processor
        self.run_content_validators = run_content_validators
        self.default_language = default_language

    def handle_line(self, line: str) -> None:
        check_for_new_fence(self.processor, self.output, line,
                            self.run_content_validators, self.default_language)

    def done(self) -> None:
        self.processor.pop()

class CodeHandler(BaseHandler):
    def __init__(self, processor: Any, output: MutableSequence[str],
                 fence: str, lang: str, run_content_validators: bool=False) -> None:
        self.processor = processor
        self.output = output
        self.fence = fence
        self.lang = lang
        self.lines: List[str] = []
        self.run_content_validators = run_content_validators

    def handle_line(self, line: str) -> None:
        if line.rstrip() == self.fence:
            self.done()
        else:
            self.lines.append(line.rstrip())

    def done(self) -> None:
        text = '\n'.join(self.lines)

        # run content validators (if any)
        if self.run_content_validators:
            validator = CODE_VALIDATORS.get(self.lang, lambda text: None)
            validator(self.lines)

        text = self.processor.format_code(self.lang, text)
        text = self.processor.placeholder(text)
        processed_lines = text.split('\n')
        self.output.append('')
        self.output.extend(processed_lines)
        self.output.append('')
        self.processor.pop()

class QuoteHandler(BaseHandler):
    def __init__(self, processor: Any, output: MutableSequence[str],
                 fence: str, default_language: Optional[str]=None) -> None:
        self.processor = processor
        self.output = output
        self.fence = fence
        self.lines: List[str] = []
        self.default_language = default_language

    def handle_line(self, line: str) -> None:
        if line.rstrip() == self.fence:
            self.done()
        else:
            check_for_new_fence(self.processor, self.lines, line, default_language=self.default_language)

    def done(self) -> None:
        text = '\n'.join(self.lines)
        text = self.processor.format_quote(text)
        processed_lines = text.split('\n')
        self.output.append('')
        self.output.extend(processed_lines)
        self.output.append('')
        self.processor.pop()


class SpoilerHandler(BaseHandler):
    def __init__(self, processor: Any, output: MutableSequence[str],
                 fence: str, spoiler_header: str) -> None:
        self.processor = processor
        self.output = output
        self.fence = fence
        self.spoiler_header = spoiler_header
        self.lines: List[str] = []

    def handle_line(self, line: str) -> None:
        if line.rstrip() == self.fence:
            self.done()
        else:
            check_for_new_fence(self.processor, self.lines, line)

    def done(self) -> None:
        if len(self.lines) == 0:
            # No content, do nothing
            return
        else:
            header = self.spoiler_header
            text = '\n'.join(self.lines)

        text = self.processor.format_spoiler(header, text)
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
        self.lines: List[str] = []

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
    def __init__(self, md: markdown.Markdown, run_content_validators: bool=False) -> None:
        markdown.preprocessors.Preprocessor.__init__(self, md)

        self.checked_for_codehilite = False
        self.run_content_validators = run_content_validators
        self.codehilite_conf: Dict[str, List[Any]] = {}

    def push(self, handler: BaseHandler) -> None:
        self.handlers.append(handler)

    def pop(self) -> None:
        self.handlers.pop()

    def run(self, lines: Iterable[str]) -> List[str]:
        """ Match and store Fenced Code Blocks in the HtmlStash. """

        output: List[str] = []

        processor = self
        self.handlers: List[BaseHandler] = []

        default_language = None
        try:
            default_language = self.md.zulip_realm.default_code_block_language
        except AttributeError:
            pass
        handler = OuterHandler(processor, output, self.run_content_validators, default_language)
        self.push(handler)

        for line in lines:
            self.handlers[-1].handle_line(line)

        while self.handlers:
            self.handlers[-1].done()

        # This fiddly handling of new lines at the end of our output was done to make
        # existing tests pass. Markdown is just kind of funny when it comes to new lines,
        # but we could probably remove this hack.
        if len(output) > 2 and output[-2] != '':
            output.append('')
        return output

    def format_code(self, lang: str, text: str) -> str:
        if lang:
            langclass = LANG_TAG.format(lang)
        else:
            langclass = ''

        # Check for code hilite extension
        if not self.checked_for_codehilite:
            for ext in self.md.registeredExtensions:
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

            code = highliter.hilite().rstrip('\n')
        else:
            code = CODE_WRAP.format(langclass, self._escape(text))

        # To support our "view in playground" feature, the frontend
        # needs to know what Pygments language was used for
        # highlighting this code block.  We record this in a data
        # attribute attached to the outer `pre` element.
        # Unfortunately, the pygments API doesn't offer a way to add
        # this, so we need to do it in a post-processing step.
        if lang:
            div_tag = lxml.html.fromstring(code)

            # For the value of our data element, we get the lexer
            # subclass name instead of directly using the language,
            # since that canonicalizes aliases (Eg: `js` and
            # `javascript` will be mapped to `JavaScript`).
            try:
                code_language = get_lexer_by_name(lang).name
            except ClassNotFound:
                # If there isn't a Pygments lexer by this name, we
                # still tag it with the user's data-code-language
                # value, since this allows hooking up a "playground"
                # for custom "languages" that aren't known to Pygments.
                #
                # The escaping isn't strictly necessary, in that the
                # characters allowed for language values should all be
                # safe, but doing escaping here makes it easy to
                # reason about.
                code_language = self._escape(lang)

            div_tag.attrib['data-code-language'] = code_language
            code = lxml.html.tostring(div_tag, encoding="unicode")
        return code

    def format_quote(self, text: str) -> str:
        paragraphs = text.split("\n\n")
        quoted_paragraphs = []
        for paragraph in paragraphs:
            lines = paragraph.split("\n")
            quoted_paragraphs.append("\n".join("> " + line for line in lines if line != ''))
        return "\n\n".join(quoted_paragraphs)

    def format_spoiler(self, header: str, text: str) -> str:
        output = []
        header_div_open_html = '<div class="spoiler-block"><div class="spoiler-header">'
        end_header_start_content_html = '</div><div class="spoiler-content" aria-hidden="true">'
        footer_html = '</div></div>'

        output.append(self.placeholder(header_div_open_html))
        output.append(header)
        output.append(self.placeholder(end_header_start_content_html))
        output.append(text)
        output.append(self.placeholder(footer_html))
        return "\n\n".join(output)

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
        return self.md.htmlStash.store(code)

    def _escape(self, txt: str) -> str:
        """ basic html escaping """
        txt = txt.replace('&', '&amp;')
        txt = txt.replace('<', '&lt;')
        txt = txt.replace('>', '&gt;')
        txt = txt.replace('"', '&quot;')
        return txt


def makeExtension(*args: Any, **kwargs: None) -> FencedCodeExtension:
    return FencedCodeExtension(kwargs)

if __name__ == "__main__":
    import doctest
    doctest.testmod()
