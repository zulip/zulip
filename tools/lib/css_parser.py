from __future__ import absolute_import
from __future__ import print_function
from six.moves import range
from typing import Callable, List, Tuple, Union

####### Helpers

class Token(object):
    def __init__(self, s, line, col):
        # type: (str, int, int) -> None
        self.s = s
        self.line = line
        self.col = col

class CssParserException(Exception):
    def __init__(self, msg, token):
        # type: (str, Token) -> None
        self.msg = msg
        self.token = token

    def __str__(self):
        # type: () -> str
        return self.msg

def find_end_brace(tokens, i, end):
    # type: (List[Token], int, int) -> int
    depth = 0
    while i < end:
        s = tokens[i].s
        if s == '{':
            depth += 1
        elif s == '}':
            if depth == 0:
                raise CssParserException('unexpected }', tokens[i])
            elif depth == 1:
                break
            depth -= 1
        i += 1
    else:
        raise CssParserException('missing }', tokens[i-1])

    return i

def get_whitespace_and_comments(tokens, i, end, line=None):
    # type: (List[Token], int, int, int) -> Tuple[int, str]

    def is_fluff_token(token):
        # type: (Token) -> bool
        s = token.s
        if ws(s[0]):
            return True
        elif s.startswith('/*'):
            # For CSS comments, the caller may pass in a line
            # number to indicate that they only want to get
            # comments on the same line.  (Subsequent comments
            # will be attached to the next actual line of code.)
            if line is None:
                return True
            if tokens[i].line == line:
                return True
        return False

    text = ''
    while (i < end) and is_fluff_token(tokens[i]):
        s = tokens[i].s
        text += s
        i += 1

    return i, text


############### Begin parsing here


def parse_sections(tokens, start, end):
    # type: (List[Token], int, int) -> CssSectionList
    i = start
    sections = []
    while i < end:
        start, pre_fluff = get_whitespace_and_comments(tokens, i, end)

        if start >= end:
            raise CssParserException('unexpected empty section', tokens[end-1])

        i = find_end_brace(tokens, start, end)

        section_end = i + 1
        i, post_fluff = get_whitespace_and_comments(tokens, i+1, end)

        section = parse_section(
            tokens=tokens,
            start=start,
            end=section_end,
            pre_fluff=pre_fluff,
            post_fluff=post_fluff
        )
        sections.append(section)

    section_list = CssSectionList(
        tokens=tokens,
        sections=sections,
    )
    return section_list

def parse_section(tokens, start, end, pre_fluff, post_fluff):
    # type: (List[Token], int, int, str, str) -> Union[CssNestedSection, CssSection]
    assert not ws(tokens[start].s)
    assert tokens[end-1].s == '}' # caller should strip trailing fluff

    first_token = tokens[start].s
    if first_token in ('@media', '@keyframes') or first_token.startswith('@-'):
        i, selector_list = parse_selectors_section(tokens, start, end) # not technically selectors
        section_list = parse_sections(tokens, i+1, end-1)
        nested_section = CssNestedSection(
            tokens=tokens,
            selector_list=selector_list,
            section_list=section_list,
            pre_fluff=pre_fluff,
            post_fluff=post_fluff,
        )
        return nested_section
    else:
        i, selector_list = parse_selectors_section(tokens, start, end)
        declaration_block = parse_declaration_block(tokens, i, end)
        section = CssSection(
            tokens=tokens,
            selector_list=selector_list,
            declaration_block=declaration_block,
            pre_fluff=pre_fluff,
            post_fluff=post_fluff,
        )
        return section

def parse_selectors_section(tokens, start, end):
    # type: (List[Token], int, int) -> Tuple[int, CssSelectorList]
    start, pre_fluff = get_whitespace_and_comments(tokens, start, end)
    assert pre_fluff == ''
    i = start
    text = ''
    while i < end and tokens[i].s != '{':
        s = tokens[i].s
        text += s
        i += 1
    selector_list = parse_selectors(tokens, start, i)
    return i, selector_list

def parse_selectors(tokens, start, end):
    # type: (List[Token], int, int) -> CssSelectorList
    i = start
    selectors = []
    while i < end:
        s = tokens[i].s
        if s == ',':
            selector = parse_selector(tokens, start, i)
            selectors.append(selector)
            i += 1
            start = i
        if s.startswith('/*'):
            raise CssParserException('Comments in selector section are not allowed', tokens[i])
        i += 1
    selector = parse_selector(tokens, start, i)
    selectors.append(selector)
    selector_list = CssSelectorList(
        tokens=tokens,
        selectors=selectors,
    )
    return selector_list

def parse_selector(tokens, start, end):
    # type: (List[Token], int, int) -> CssSelector
    i, pre_fluff = get_whitespace_and_comments(tokens, start, end)
    levels = []
    last_i = None
    while i < end:
        token = tokens[i]
        i += 1
        if not ws(token.s[0]):
            last_i = i
            levels.append(token)

    if last_i is None:
        raise CssParserException('Missing selector', tokens[-1])

    assert last_i is not None
    start, post_fluff = get_whitespace_and_comments(tokens, last_i, end)
    selector = CssSelector(
        tokens=tokens,
        pre_fluff=pre_fluff,
        post_fluff=post_fluff,
        levels=levels,
    )
    return selector

def parse_declaration_block(tokens, start, end):
    # type: (List[Token], int, int) -> CssDeclarationBlock
    assert tokens[start].s == '{' # caller should strip leading fluff
    assert tokens[end-1].s == '}' # caller should strip trailing fluff
    i = start + 1
    declarations = []
    while i < end-1:
        start = i
        i, _ = get_whitespace_and_comments(tokens, i, end)
        while (i < end) and (tokens[i].s != ';'):
            i += 1
        if i < end:
            i, _ = get_whitespace_and_comments(tokens, i+1, end, line=tokens[i].line)
        declaration = parse_declaration(tokens, start, i)
        declarations.append(declaration)

    declaration_block = CssDeclarationBlock(
        tokens=tokens,
        declarations=declarations,
    )
    return declaration_block

def parse_declaration(tokens, start, end):
    # type: (List[Token], int, int) -> CssDeclaration
    i, pre_fluff = get_whitespace_and_comments(tokens, start, end)

    if (i >= end) or (tokens[i].s == '}'):
        raise CssParserException('Empty declaration or missing semicolon', tokens[i-1])

    css_property = tokens[i].s
    if tokens[i+1].s != ':':
        raise CssParserException('We expect a colon here', tokens[i])
    i += 2
    start = i
    while (i < end) and (tokens[i].s != ';') and (tokens[i].s != '}'):
        i += 1
    css_value = parse_value(tokens, start, i)
    semicolon = (i < end) and (tokens[i].s == ';')
    if semicolon:
        i += 1
    _, post_fluff = get_whitespace_and_comments(tokens, i, end)
    declaration = CssDeclaration(
        tokens=tokens,
        pre_fluff=pre_fluff,
        post_fluff=post_fluff,
        css_property=css_property,
        css_value=css_value,
        semicolon=semicolon,
    )
    return declaration

def parse_value(tokens, start, end):
    # type: (List[Token], int, int) -> CssValue
    i, pre_fluff = get_whitespace_and_comments(tokens, start, end)
    if i < end:
        value = tokens[i]
    else:
        raise CssParserException('Missing value', tokens[i-1])
    i, post_fluff = get_whitespace_and_comments(tokens, i+1, end)
    return CssValue(
        tokens=tokens,
        value=value,
        pre_fluff=pre_fluff,
        post_fluff=post_fluff,
    )


#### Begin CSS classes here

class CssSectionList(object):
    def __init__(self, tokens, sections):
        # type: (List[Token], List[Union[CssNestedSection, CssSection]]) -> None
        self.tokens = tokens
        self.sections = sections

    def text(self):
        # type: () -> str
        res = ''.join(section.text() for section in self.sections)
        return res

class CssNestedSection(object):
    def __init__(self, tokens, selector_list, section_list, pre_fluff, post_fluff):
        # type: (List[Token], CssSelectorList, CssSectionList, str, str) -> None
        self.tokens = tokens
        self.selector_list = selector_list
        self.section_list = section_list
        self.pre_fluff = pre_fluff
        self.post_fluff = post_fluff

    def text(self):
        # type: () -> str
        res = ''
        res += self.pre_fluff
        res += self.selector_list.text()
        res += '{'
        res += self.section_list.text()
        res += '}'
        res += self.post_fluff
        return res

class CssSection(object):
    def __init__(self, tokens, selector_list, declaration_block, pre_fluff, post_fluff):
        # type: (List[Token], CssSelectorList, CssDeclarationBlock, str, str) -> None
        self.tokens = tokens
        self.selector_list = selector_list
        self.declaration_block = declaration_block
        self.pre_fluff = pre_fluff
        self.post_fluff = post_fluff

    def text(self):
        # type: () -> str
        res = ''
        res += self.pre_fluff
        res += self.selector_list.text()
        res += self.declaration_block.text()
        res += self.post_fluff
        return res

class CssSelectorList(object):
    def __init__(self, tokens, selectors):
        # type: (List[Token], List[CssSelector]) -> None
        self.tokens = tokens
        self.selectors = selectors

    def text(self):
        # type: () -> str
        res = ','.join(sel.text() for sel in self.selectors)
        return res

class CssSelector(object):
    def __init__(self, tokens, pre_fluff, post_fluff, levels):
        # type: (List[Token],str, str, List[Token]) -> None
        self.tokens = tokens
        self.pre_fluff = pre_fluff
        self.post_fluff = post_fluff
        self.levels = levels

    def text(self):
        # type: () -> str
        res = ''
        res += self.pre_fluff
        res += ' '.join(level.s for level in self.levels)
        res += self.post_fluff
        return res

class CssDeclarationBlock(object):
    def __init__(self, tokens, declarations):
        # type: (List[Token], List[CssDeclaration]) -> None
        self.tokens = tokens
        self.declarations = declarations

    def text(self):
        # type: () -> str
        res = '{'
        for declaration in self.declarations:
            res += declaration.text()
        res += '}'
        return res

class CssDeclaration(object):
    def __init__(self, tokens, pre_fluff, post_fluff, css_property, css_value, semicolon):
        # type: (List[Token], str, str, str, CssValue, bool) -> None
        self.tokens = tokens
        self.pre_fluff = pre_fluff
        self.post_fluff = post_fluff
        self.css_property = css_property
        self.css_value = css_value
        self.semicolon = semicolon

    def text(self):
        # type: () -> str
        res = ''
        res += self.pre_fluff
        res += self.css_property
        res += ':'
        value_text = self.css_value.text()
        if '\n' in value_text:
            # gradient values can be multi-line
            res += value_text.rstrip()
        else:
            res += ' '
            res += value_text.strip()
        res += ';'
        res += self.post_fluff
        return res

class CssValue(object):
    def __init__(self, tokens, value, pre_fluff, post_fluff):
        # type: (List[Token], Token, str, str) -> None
        self.value = value
        self.pre_fluff = pre_fluff
        self.post_fluff = post_fluff
        assert pre_fluff.strip() == ''

    def text(self):
        # type: () -> str
        return self.pre_fluff + self.value.s + self.post_fluff

def parse(text):
    # type: (str) -> CssSectionList
    tokens = tokenize(text)
    section_list = parse_sections(tokens, 0, len(tokens))
    return section_list

#### Begin tokenizer section here

def ws(c):
    # type: (str) -> bool
    return c in ' \t\n'

def tokenize(text):
    # type: (str) -> List[Token]

    class State(object):
        def __init__(self):
            # type: () -> None
            self.i = 0
            self.line = 1
            self.col = 1

    tokens = []
    state = State()

    def add_token(s, state):
        # type: (str, State) -> None
        # deep copy data
        token = Token(s=s, line=state.line, col=state.col)
        tokens.append(token)

    def legal(offset):
        # type: (int) -> bool
        return state.i + offset < len(text)

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

    def get_field(terminator):
        # type: (Callable[[str], bool]) -> str
        offset = 0
        paren_level = 0
        while legal(offset) and (paren_level or not terminator(text[state.i + offset])):
            c = text[state.i + offset]
            if c == '(':
                paren_level += 1
            elif c == ')':
                paren_level -= 1
            offset += 1
        return text[state.i:state.i+offset]

    in_property = False
    in_value = False
    in_media_line = False
    starting_media_section = False
    while state.i < len(text):
        c = text[state.i]

        if c in '{};:,':
            if c == ':':
                in_property = False
                in_value = True
            elif c == ';':
                in_property = True
                in_value = False
            elif c in '{':
                if starting_media_section:
                    starting_media_section = False
                else:
                    in_property = True
            elif c == '}':
                in_property = False
            s = c

        elif ws(c):
            terminator = lambda c: not ws(c)
            s = get_field(terminator)

        elif looking_at('/*'):
            # hacky
            old_i = state.i
            while (state.i < len(text)) and not looking_at('*/'):
                state.i += 1
            if not looking_at('*/'):
                raise CssParserException('unclosed comment', tokens[-1])
            s = text[old_i:state.i+2]
            state.i = old_i

        elif looking_at('@media'):
            s = '@media'
            in_media_line = True
            starting_media_section = True

        elif in_media_line:
            in_media_line = False
            terminator = lambda c: c == '{'
            s = get_field(terminator)
            s = s.rstrip()

        elif in_property:
            terminator = lambda c: ws(c) or c in ':{'
            s = get_field(terminator)

        elif in_value:
            in_value = False
            in_property = True
            terminator = lambda c: c in ';}'
            s = get_field(terminator)
            s = s.rstrip()

        else:
            terminator = lambda c: ws(c) or c == ','
            s = get_field(terminator)

        add_token(s, state)
        advance(len(s))

    return tokens
