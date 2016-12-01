from __future__ import absolute_import
from __future__ import print_function
from typing import Callable, Optional
from six.moves import range
import re

class TemplateParserException(Exception):
    # TODO: Have callers pass in line numbers.
    pass

class TokenizerState(object):
    def __init__(self):
        # type: () -> None
        self.i = 0
        self.line = 1
        self.col = 1

class Token(object):
    def __init__(self, kind, s, tag, line, col):
        # type: (str, str, str, int, int) -> None
        self.kind = kind
        self.s = s
        self.tag = tag
        self.line = line
        self.col = col

def tokenize(text):
    # type: (str) -> List[Token]
    def advance(n):
        # type: (int) -> None
        for _ in range(n):
            state.i += 1
            if state.i >= 0 and text[state.i - 1] == '\n':
                state.line += 1
                state.col = 1
            else:
                state.col += 1

    def looking_at(s):
        # type: (str) -> bool
        return text[state.i:state.i+len(s)] == s

    def looking_at_html_start():
        # type: () -> bool
        return looking_at("<") and not looking_at("</")

    def looking_at_html_end():
        # type: () -> bool
        return looking_at("</")

    def looking_at_handlebars_start():
        # type: () -> bool
        return looking_at("{{#") or looking_at("{{^")

    def looking_at_handlebars_end():
        # type: () -> bool
        return looking_at("{{/")

    def looking_at_django_start():
        # type: () -> bool
        return looking_at("{% ") and not looking_at("{% end")

    def looking_at_django_end():
        # type: () -> bool
        return looking_at("{% end")

    state = TokenizerState()
    tokens = []

    while state.i < len(text):
        if looking_at_html_start():
            s = get_html_tag(text, state.i)
            tag_parts = s[1:-1].split()

            if not tag_parts:
                raise TemplateParserException("Tag name missing")

            tag = tag_parts[0]

            if is_special_html_tag(s, tag):
                kind = 'html_special'
            elif s.endswith('/>'):
                kind = 'html_singleton'
            else:
                kind = 'html_start'
        elif looking_at_html_end():
            s = get_html_tag(text, state.i)
            tag = s[2:-1]
            kind = 'html_end'
        elif looking_at_handlebars_start():
            s = get_handlebars_tag(text, state.i)
            tag = s[3:-2].split()[0]
            kind = 'handlebars_start'
        elif looking_at_handlebars_end():
            s = get_handlebars_tag(text, state.i)
            tag = s[3:-2]
            kind = 'handlebars_end'
        elif looking_at_django_start():
            s = get_django_tag(text, state.i)
            tag = s[3:-2].split()[0]
            kind = 'django_start'
        elif looking_at_django_end():
            s = get_django_tag(text, state.i)
            tag = s[6:-3]
            kind = 'django_end'
        else:
            advance(1)
            continue

        token = Token(
            kind=kind,
            s=s,
            tag=tag,
            line=state.line,
            col=state.col,
        )
        tokens.append(token)
        advance(len(s))

    return tokens

def validate(fn=None, text=None, check_indent=True):
    # type: (Optional[str], Optional[str], bool) -> None
    assert fn or text

    if fn is None:
        fn = '<in memory file>'

    if text is None:
        text = open(fn).read()

    tokens = tokenize(text)

    class State(object):
        def __init__(self, func):
            # type: (Callable[[Token], None]) -> None
            self.depth = 0
            self.matcher = func

    def no_start_tag(token):
        # type: (Token) -> None
        raise TemplateParserException('''
            No start tag
            fn: %s
            end tag:
                %s
                line %d, col %d
            ''' % (fn, token.tag, token.line, token.col))

    state = State(no_start_tag)

    def start_tag_matcher(start_token):
        # type: (Token) -> None
        state.depth += 1
        start_tag = start_token.tag
        start_line = start_token.line
        start_col = start_token.col

        old_matcher = state.matcher

        def f(end_token):
            # type: (Token) -> None

            end_tag = end_token.tag
            end_line = end_token.line
            end_col = end_token.col

            if start_tag == 'a':
                max_lines = 3
            else:
                max_lines = 1

            problem = None
            if (start_tag == 'code') and (end_line == start_line + 1):
                problem = 'Code tag is split across two lines.'
            if start_tag != end_tag:
                problem = 'Mismatched tag.'
            elif check_indent and (end_line > start_line + max_lines):
                if end_col != start_col:
                    problem = 'Bad indentation.'
            if problem:
                raise TemplateParserException('''
                    fn: %s
                    %s
                    start:
                        %s
                        line %d, col %d
                    end tag:
                        %s
                        line %d, col %d
                    ''' % (fn, problem, start_token.s, start_line, start_col, end_tag, end_line, end_col))
            state.matcher = old_matcher
            state.depth -= 1
        state.matcher = f

    for token in tokens:
        kind = token.kind
        tag = token.tag

        if kind == 'html_start':
            start_tag_matcher(token)
        elif kind == 'html_end':
            state.matcher(token)

        elif kind == 'handlebars_start':
            start_tag_matcher(token)
        elif kind == 'handlebars_end':
            state.matcher(token)

        elif kind == 'django_start':
            if is_django_block_tag(tag):
                start_tag_matcher(token)
        elif kind == 'django_end':
            state.matcher(token)

    if state.depth != 0:
        raise TemplateParserException('Missing end tag')

def is_special_html_tag(s, tag):
    # type: (str, str) -> bool
    return (s.startswith('<!--') or
            tag in ['link', 'meta', '!DOCTYPE'])

def is_django_block_tag(tag):
    # type: (str) -> bool
    return tag in [
        'autoescape',
        'block',
        'comment',
        'for',
        'if',
        'ifequal',
        'verbatim',
        'blocktrans',
        'trans',
        'raw',
    ]

def get_handlebars_tag(text, i):
    # type: (str, int) -> str
    end = i + 2
    while end < len(text) - 1 and text[end] != '}':
        end += 1
    if text[end] != '}' or text[end+1] != '}':
        raise TemplateParserException('Tag missing }}')
    s = text[i:end+2]
    return s

def get_django_tag(text, i):
    # type: (str, int) -> str
    end = i + 2
    while end < len(text) - 1 and text[end] != '%':
        end += 1
    if text[end] != '%' or text[end+1] != '}':
        raise TemplateParserException('Tag missing %}')
    s = text[i:end+2]
    return s

def get_html_tag(text, i):
    # type: (str, int) -> str
    quote_count = 0
    end = i + 1
    while end < len(text) and (text[end] != '>' or quote_count % 2 != 0):
        if text[end] == '"':
            quote_count += 1
        end += 1
    if end == len(text) or text[end] != '>':
        raise TemplateParserException('Tag missing >')
    s = text[i:end+1]
    return s
