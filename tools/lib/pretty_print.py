import subprocess
from typing import List, Optional, Set

from zulint.printer import ENDC, GREEN

from .template_parser import Token, is_django_block_tag, tokenize


def requires_indent(line: str) -> bool:
    line = line.lstrip()
    return line.startswith("<")


def open_token(token: Token) -> bool:
    if token.kind in (
        "handlebars_start",
        "html_start",
    ):
        return True

    if token.kind in (
        "django_start",
        "jinja2_whitespace_stripped_start",
        "jinja2_whitespace_stripped_type2_start",
    ):
        return is_django_block_tag(token.tag)

    return False


def close_token(token: Token) -> bool:
    return token.kind in (
        "django_end",
        "handlebars_end",
        "html_end",
        "jinja2_whitespace_stripped_end",
    )


def else_token(token: Token) -> bool:
    return token.kind in (
        "django_else",
        "handlebars_else",
    )


def pop_unused_tokens(tokens: List[Token], row: int) -> bool:
    was_closed = False
    while tokens and tokens[-1].line <= row:
        token = tokens.pop()
        if close_token(token):
            was_closed = True
    return was_closed


def indent_pref(row: int, tokens: List[Token], line: str) -> str:
    opens = 0
    closes = 0
    is_else = False

    while tokens and tokens[-1].line == row:
        token = tokens.pop()
        if open_token(token):
            opens += 1
        elif close_token(token):
            closes += 1
        elif else_token(token):
            is_else = True

    if is_else:
        if opens and closes:
            return "neutral"
        return "else"

    i = opens - closes
    if i == 0:
        return "neutral"
    elif i == 1:
        return "open"
    elif i == -1:
        return "close"
    else:
        print(i, opens, closes)
        raise Exception(f"too many tokens on row {row}")


def indent_level(s: str) -> int:
    return len(s) - len(s.lstrip())


def same_indent(s1: str, s2: str) -> bool:
    return indent_level(s1) == indent_level(s2)


def next_non_blank_line(lines: List[str], i: int) -> str:
    next_line = ""
    for j in range(i + 1, len(lines)):
        next_line = lines[j]
        if next_line.strip() != "":
            break
    return next_line


def get_exempted_lines(tokens: List[Token]) -> Set[int]:
    exempted = set()
    for code_tag in ("code", "pre", "script"):
        for token in tokens:
            if token.kind == "html_start" and token.tag == code_tag:
                start: Optional[int] = token.line

            if token.kind == "html_end" and token.tag == code_tag:
                # The pretty printer expects well-formed HTML, even
                # if it's strangely formatted, so we expect start
                # to be None.
                assert start is not None

                # We leave code blocks completely alone, including
                # the start and end tags.
                for i in range(start, token.line + 1):
                    exempted.add(i)
                    start = None
    return exempted


def pretty_print_html(html: str) -> str:
    tokens = tokenize(html)

    exempted_lines = get_exempted_lines(tokens)

    tokens.reverse()
    lines = html.split("\n")

    open_offsets: List[str] = []
    formatted_lines = []
    next_offset: str = ""
    tag_end_row: Optional[int] = None
    tag_continuation_offset = ""

    def line_offset(row: int, line: str, next_line: str) -> Optional[str]:
        nonlocal next_offset
        nonlocal tag_end_row
        nonlocal tag_continuation_offset

        if tag_end_row and row < tag_end_row:
            was_closed = pop_unused_tokens(tokens, row)
            if was_closed:
                next_offset = open_offsets.pop()
            return tag_continuation_offset

        while tokens and tokens[-1].line < row:
            token = tokens.pop()

        offset = next_offset
        if tokens:
            token = tokens[-1]
            if token.kind == "indent":
                token = tokens[-2]
            if (
                token.line == row
                and token.line_span > 1
                and token.kind not in ("template_var", "text")
            ):
                if token.kind in ("django_comment", "handlebar_comment", "html_comment"):
                    tag_continuation_offset = offset
                else:
                    tag_continuation_offset = offset + "  "
                tag_end_row = row + token.line_span

        pref = indent_pref(row, tokens, line)
        if pref == "open":
            if same_indent(line, next_line) and not requires_indent(line):
                next_offset = offset
            else:
                next_offset = offset + " " * 4
            open_offsets.append(offset)
        elif pref == "else":
            offset = open_offsets[-1]
            if same_indent(line, next_line):
                next_offset = offset
            else:
                next_offset = offset + " " * 4
        elif pref == "close":
            offset = open_offsets.pop()
            next_offset = offset
        return offset

    def adjusted_line(row: int, line: str, next_line: str) -> str:
        if line.strip() == "":
            return ""

        offset = line_offset(row, line, next_line)

        if row in exempted_lines:
            return line.rstrip()

        if offset is None:
            return line.rstrip()

        return offset + line.strip()

    for i, line in enumerate(lines):
        # We use 1-based indexing for both rows and columns.
        next_line = next_non_blank_line(lines, i)
        row = i + 1
        formatted_lines.append(adjusted_line(row, line, next_line))

    return "\n".join(formatted_lines)


def validate_indent_html(fn: str, fix: bool) -> bool:
    with open(fn) as f:
        html = f.read()
    phtml = pretty_print_html(html)
    if not html.split("\n") == phtml.split("\n"):
        if fix:
            print(GREEN + f"Automatically fixing indentation for {fn}" + ENDC)
            with open(fn, "w") as f:
                f.write(phtml)
            # Since we successfully fixed the issues, we return True.
            return True
        print(
            "Invalid indentation detected in file: "
            f"{fn}\nDiff for the file against expected indented file:",
            flush=True,
        )
        subprocess.run(["diff", fn, "-"], input=phtml, universal_newlines=True)
        print()
        print("This problem can be fixed with the `--fix` option.")
        return False
    return True
