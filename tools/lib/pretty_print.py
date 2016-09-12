from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from .template_parser import (
    tokenize,
)

def pretty_print_html(html, num_spaces=4):
    # type: (str, int) -> str
    # We use 1-based indexing for both rows and columns.
    tokens = tokenize(html)

    # We will keep a stack of "start" tags so that we know
    # when HTML ranges end.  Note that some start tags won't
    # be blocks from an indentation standpoint.
    stack = [] # type: List[Dict[str, Any]]

    # Seed our stack with a pseudo entry to make depth calculations
    # easier.
    info = dict(
        block=False,
        depth=-1,
        line=-1)
    stack.append(info)

    # Our main job is to figure out offsets that we use to nudge lines
    # over by.
    offsets = {} # type: Dict[int, int]

    # Loop through our start/end tokens, and calculate offsets.  As
    # we proceed, we will push/pop info dictionaries on/off a stack.
    for token in tokens:
        if token.kind in ('html_start'):
            # An HTML start tag should only cause a new indent if we
            # are on a new line.
            is_block = token.line > stack[-1]['line']

            if is_block:
                new_depth = stack[-1]['depth'] + 1
                offset = (1 + new_depth * num_spaces) - token.col
                info = dict(
                    block=True,
                    depth=new_depth,
                    line=token.line,
                    offset=offset,
                )
            else:
                info = dict(block=False)
            stack.append(info)
        elif token.kind in ('html_end'):
            info = stack.pop()
            if info['block'] and info['offset']:
                # We are at the end of an indentation block.  We
                # assume the whole block was formatted ok before, just
                # possibly at an indentation that we don't like, so we
                # nudge over all lines in the block by the same offset.
                start_line = info['line']
                end_line = token.line
                for line_num in range(start_line, end_line + 1):
                    # Be careful not to override offsets that happened
                    # deeper in the HTML within our block.
                    if line_num not in offsets:
                        offsets[line_num] = info['offset']

    # Now that we have all of our offsets calculated, we can just
    # join all our lines together, fixing up offsets as needed.
    formatted_lines = []
    for i, line in enumerate(html.split('\n')):
        row = i + 1
        offset = offsets.get(row, 0)
        pretty_line = line
        if line.strip() == '':
            pretty_line = ''
        else:
            if offset > 0:
                pretty_line = (' ' * offset) + pretty_line
            elif offset < 0:
                pretty_line = pretty_line[-1 * offset:]
                assert line.strip() == pretty_line.strip()
        formatted_lines.append(pretty_line)

    return '\n'.join(formatted_lines)
