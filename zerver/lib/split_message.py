import re

MAX_SPLIT_MESSAGE_PARTS = 20

JS_WHITESPACE_EXCEPT_NEWLINE = "\t\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
JS_WHITESPACE = JS_WHITESPACE_EXCEPT_NEWLINE + "\n"

SPLIT_DELIMITER_RE = re.compile(
    rf"\n[{JS_WHITESPACE_EXCEPT_NEWLINE}]*\n[{JS_WHITESPACE_EXCEPT_NEWLINE}]*\n"
)
LEADING_BLANK_LINES_RE = re.compile(rf"^(?:[{JS_WHITESPACE}]*\n)+")

FENCE_RE = re.compile(r"^(~{3,}|`{3,})[ ]*(\{?\.?([a-zA-Z0-9_+-./#]*)\}?)[ ]*(\{?\.?([^~`]*)\}?)\Z")

INDENTED_CODE_PREFIX = " " * 4


def get_code_block_ranges(content: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    offset = 0
    fence: str | None = None
    fence_start = 0
    indent_start: int | None = None
    indent_end = 0
    prev_line_blank = True

    for line in content.split("\n"):
        line_start = offset
        line_end = offset + len(line)
        offset = line_end + 1

        if fence is not None:
            if line == fence:
                ranges.append((fence_start, line_end))
                fence = None
            prev_line_blank = False
            continue

        fence_match = FENCE_RE.match(line)
        if fence_match:
            if indent_start is not None:
                ranges.append((indent_start, indent_end))
                indent_start = None
            fence = fence_match.group(1)
            fence_start = line_start
            prev_line_blank = False
            continue

        if line.strip(JS_WHITESPACE) == "":
            prev_line_blank = True
            continue

        if (line.startswith((INDENTED_CODE_PREFIX, "\t"))) and (
            indent_start is not None or prev_line_blank
        ):
            if indent_start is None:
                indent_start = line_start
            indent_end = line_end
        elif indent_start is not None:
            ranges.append((indent_start, indent_end))
            indent_start = None
        prev_line_blank = False

    if fence is not None:
        ranges.append((fence_start, len(content)))
    elif indent_start is not None:
        ranges.append((indent_start, indent_end))
    return ranges


def delimiter_index_outside_code_block(content: str) -> int:
    ranges = get_code_block_ranges(content)
    position = 0
    while (match := SPLIT_DELIMITER_RE.search(content, position)) is not None:
        if not any(start <= match.start() + 1 < end for start, end in ranges):
            return match.start()
        position = match.start() + 1
    return -1


def trim_except_whitespace_before_text(content: str) -> str:
    return LEADING_BLANK_LINES_RE.sub("", content).rstrip(JS_WHITESPACE)


def split_message_content(content: str) -> list[str]:
    parts: list[str] = []
    remaining_content = content
    while remaining_content:
        message_content = trim_except_whitespace_before_text(remaining_content)
        index = delimiter_index_outside_code_block(message_content)
        if index == -1:
            parts.append(message_content)
            break
        parts.append(message_content[:index])
        remaining_content = message_content[index:]
    return parts
