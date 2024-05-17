import subprocess
from typing import List, Optional

from zulint.printer import BOLDRED, CYAN, ENDC, GREEN

from .template_parser import Token


def shift_indents_to_the_next_tokens(tokens: List[Token]) -> None:
    """
    During the parsing/validation phase, it's useful to have separate
    tokens for "indent" chunks, but during pretty printing, we like
    to attach an `.indent` field to the substantive node, whether
    it's an HTML tag or template directive or whatever.
    """
    tokens[0].indent = ""

    for i, token in enumerate(tokens[:-1]):
        next_token = tokens[i + 1]

        if token.kind == "indent":
            next_token.indent = token.s
            token.new_s = ""

        if token.kind == "newline" and next_token.kind != "indent":
            next_token.indent = ""


def token_allows_children_to_skip_indents(token: Token) -> bool:
    # To avoid excessive indentation in templates with other
    # conditionals, we don't require extra indentation for template
    # logic blocks don't contain further logic as direct children.

    # Each blocks are excluded from this rule, since we want loops to
    # stand out.
    if token.tag == "each":
        return False

    return token.kind in ("django_start", "handlebars_start") or token.tag == "a"


def adjust_block_indentation(tokens: List[Token], fn: str) -> None:
    start_token: Optional[Token] = None

    for token in tokens:
        if token.kind in ("indent", "whitespace", "newline"):
            continue

        if token.tag in ("code", "pre"):
            continue

        # print(token.line, repr(start_token.indent) if start_token else "?", repr(token.indent), token.s, token.end_token and "start", token.start_token and "end")

        if token.tag == "else":
            assert token.start_token
            if token.indent is not None:
                token.indent = token.start_token.indent
            continue

        if start_token and token.indent is not None:
            if (
                not start_token.indent_is_final
                and token.indent == start_token.orig_indent
                and token_allows_children_to_skip_indents(start_token)
            ):
                start_token.child_indent = start_token.indent
            start_token.indent_is_final = True

        # Detect start token by its having a end token
        if token.end_token:
            if token.indent is not None:
                token.orig_indent = token.indent
                if start_token:
                    assert start_token.child_indent is not None
                    token.indent = start_token.child_indent
                else:
                    token.indent = ""
                token.child_indent = token.indent + "    "
            token.parent_token = start_token
            start_token = token
            continue

        # Detect end token by its having a start token
        if token.start_token:
            if start_token != token.start_token:
                raise AssertionError(
                    f"""
                    {token.kind} was unexpected in {token.s}
                    in row {token.line} of {fn}
                    """
                )

            if token.indent is not None:
                token.indent = start_token.indent
            start_token = start_token.parent_token
            continue

        if token.indent is None:
            continue

        if start_token is None:
            token.indent = ""
            continue

        if start_token.child_indent is not None:
            token.indent = start_token.child_indent


def fix_indents_for_multi_line_tags(tokens: List[Token]) -> None:
    def fix(frag: str) -> str:
        frag = frag.strip()
        return continue_indent + frag if frag else ""

    for token in tokens:
        if token.kind == "code":
            continue

        if token.line_span == 1 or token.indent is None:
            continue

        if token.kind in ("django_comment", "handlebars_comment", "html_comment", "text"):
            continue_indent = token.indent
        else:
            continue_indent = token.indent + "  "

        frags = token.new_s.split("\n")

        token.new_s = frags[0] + "\n" + "\n".join(fix(frag) for frag in frags[1:])


def apply_token_indents(tokens: List[Token]) -> None:
    for token in tokens:
        if token.indent:
            token.new_s = token.indent + token.new_s


def pretty_print_html(tokens: List[Token], fn: str) -> str:
    for token in tokens:
        token.new_s = token.s

    shift_indents_to_the_next_tokens(tokens)
    adjust_block_indentation(tokens, fn)
    fix_indents_for_multi_line_tags(tokens)
    apply_token_indents(tokens)

    return "".join(token.new_s for token in tokens)


def numbered_lines(s: str) -> str:
    return "".join(f"{i + 1: >5} {line}\n" for i, line in enumerate(s.split("\n")))


def validate_indent_html(fn: str, tokens: List[Token], fix: bool) -> bool:
    with open(fn) as f:
        html = f.read()
    phtml = pretty_print_html(tokens, fn)
    if html.split("\n") != phtml.split("\n"):
        if fix:
            print(GREEN + f"Automatically fixing indentation for {fn}" + ENDC)
            with open(fn, "w") as f:
                f.write(phtml)
            # Since we successfully fixed the issues, we return True.
            return True
        print(
            f"""
{BOLDRED}PROBLEM{ENDC}: formatting errors in {fn}

Here is how we would like you to format
{CYAN}{fn}{ENDC}:
---
{numbered_lines(phtml)}
---

Here is the diff that you should either execute in your editor
or apply automatically with the --fix option.

({CYAN}Scroll up{ENDC} to see how we would like the file formatted.)

Proposed {BOLDRED}diff{ENDC} for {CYAN}{fn}{ENDC}:
            """,
            flush=True,
        )
        subprocess.run(["diff", fn, "-"], input=phtml, text=True, check=False)
        print(
            f"""
---

{BOLDRED}PROBLEM!!!{ENDC}

    You have formatting errors in {CYAN}{fn}{ENDC}
    (Usually these messages are related to indentation.)

This problem can be fixed with the {CYAN}`--fix`{ENDC} option.
Scroll up for more details about {BOLDRED}what you need to fix ^^^{ENDC}.
            """
        )
        return False
    return True
