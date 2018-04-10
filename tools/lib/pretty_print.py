
from typing import Any, Dict, List

from .template_parser import (
    tokenize,
    Token,
    is_django_block_tag,
)
import subprocess

def pretty_print_html(html, num_spaces=4):
    # type: (str, int) -> str
    # We use 1-based indexing for both rows and columns.
    tokens = tokenize(html)
    lines = html.split('\n')

    # We will keep a stack of "start" tags so that we know
    # when HTML ranges end.  Note that some start tags won't
    # be blocks from an indentation standpoint.
    stack = []  # type: List[Dict[str, Any]]

    # Seed our stack with a pseudo entry to make depth calculations
    # easier.
    info = dict(
        block=False,
        depth=-1,
        line=-1,
        token_kind='html_start',
        tag='html',
        extra_indent=0,
        ignore_lines=[])  # type: Dict[str, Any]
    stack.append(info)

    # Our main job is to figure out offsets that we use to nudge lines
    # over by.
    offsets = {}  # type: Dict[int, int]

    # Loop through our start/end tokens, and calculate offsets.  As
    # we proceed, we will push/pop info dictionaries on/off a stack.
    for token in tokens:

        if token.kind in ('html_start', 'handlebars_start', 'handlebars_singleton',
                          'html_singleton', 'django_start') and stack[-1]['tag'] != 'pre':
            # An HTML start tag should only cause a new indent if we
            # are on a new line.
            if (token.tag not in ('extends', 'include', 'else', 'elif') and
                    (is_django_block_tag(token.tag) or
                        token.kind != 'django_start')):
                is_block = token.line > stack[-1]['line']

                if is_block:
                    if (((token.kind == 'handlebars_start' and
                            stack[-1]['token_kind'] == 'handlebars_start') or
                            (token.kind == 'django_start' and
                             stack[-1]['token_kind'] == 'django_start')) and
                            not stack[-1]['indenting']):
                        info = stack.pop()
                        info['depth'] = info['depth'] + 1
                        info['indenting'] = True
                        info['adjust_offset_until'] = token.line
                        stack.append(info)
                    new_depth = stack[-1]['depth'] + 1
                    extra_indent = stack[-1]['extra_indent']
                    line = lines[token.line - 1]
                    adjustment = len(line)-len(line.lstrip()) + 1
                    offset = (1 + extra_indent + new_depth * num_spaces) - adjustment
                    info = dict(
                        block=True,
                        depth=new_depth,
                        actual_depth=new_depth,
                        line=token.line,
                        tag=token.tag,
                        token_kind=token.kind,
                        line_span=token.line_span,
                        offset=offset,
                        extra_indent=token.col - adjustment + extra_indent,
                        extra_indent_prev=extra_indent,
                        adjustment=adjustment,
                        indenting=True,
                        adjust_offset_until=token.line,
                        ignore_lines=[]
                    )
                    if token.kind in ('handlebars_start', 'django_start'):
                        info.update(dict(depth=new_depth - 1, indenting=False))
                else:
                    info = dict(
                        block=False,
                        depth=stack[-1]['depth'],
                        actual_depth=stack[-1]['depth'],
                        line=token.line,
                        tag=token.tag,
                        token_kind=token.kind,
                        extra_indent=stack[-1]['extra_indent'],
                        ignore_lines=[]
                    )
                stack.append(info)
        elif (token.kind in ('html_end', 'handlebars_end', 'html_singleton_end',
                             'django_end', 'handlebars_singleton_end') and
              (stack[-1]['tag'] != 'pre' or token.tag == 'pre')):
            info = stack.pop()
            if info['block']:
                # We are at the end of an indentation block.  We
                # assume the whole block was formatted ok before, just
                # possibly at an indentation that we don't like, so we
                # nudge over all lines in the block by the same offset.
                start_line = info['line']
                end_line = token.line
                if token.tag == 'pre':
                    offsets[start_line] = 0
                    offsets[end_line] = 0
                    stack[-1]['ignore_lines'].append(start_line)
                    stack[-1]['ignore_lines'].append(end_line)
                else:
                    offsets[start_line] = info['offset']
                    line = lines[token.line - 1]
                    adjustment = len(line)-len(line.lstrip()) + 1
                    if adjustment == token.col and token.kind != 'html_singleton_end':
                        offsets[end_line] = (info['offset'] +
                                             info['adjustment'] -
                                             adjustment +
                                             info['extra_indent'] -
                                             info['extra_indent_prev'])
                    elif (start_line + info['line_span'] - 1 == end_line and
                            info['line_span'] > 1):
                        offsets[end_line] = (1 + info['extra_indent'] +
                                             (info['depth'] + 1) * num_spaces) - adjustment
                        # We would like singleton tags and tags which spread over
                        # multiple lines to have 2 space indentation.
                        offsets[end_line] -= 2
                    elif token.line != info['line']:
                        offsets[end_line] = info['offset']
                if token.tag != 'pre' and token.tag != 'script':
                    for line_num in range(start_line + 1, end_line):
                        # Be careful not to override offsets that happened
                        # deeper in the HTML within our block.
                        if line_num not in offsets:
                            line = lines[line_num - 1]
                            new_depth = info['depth'] + 1
                            if (line.lstrip().startswith('{{else}}') or
                                    line.lstrip().startswith('{% else %}') or
                                    line.lstrip().startswith('{% elif')):
                                new_depth = info['actual_depth']
                            extra_indent = info['extra_indent']
                            adjustment = len(line)-len(line.lstrip()) + 1
                            offset = (1 + extra_indent + new_depth * num_spaces) - adjustment
                            if line_num <= start_line + info['line_span'] - 1:
                                # We would like singleton tags and tags which spread over
                                # multiple lines to have 2 space indentation.
                                offset -= 2
                            offsets[line_num] = offset
                        elif (token.kind in ('handlebars_end', 'django_end') and
                                info['indenting'] and
                                line_num < info['adjust_offset_until'] and
                                line_num not in info['ignore_lines']):
                            offsets[line_num] += num_spaces
                elif token.tag != 'pre':
                    for line_num in range(start_line + 1, end_line):
                        if line_num not in offsets:
                            offsets[line_num] = info['offset']
                else:
                    for line_num in range(start_line + 1, end_line):
                        if line_num not in offsets:
                            offsets[line_num] = 0
                            stack[-1]['ignore_lines'].append(line_num)

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


def validate_indent_html(fn):
    # type: (str) -> int
    file = open(fn)
    html = file.read()
    phtml = pretty_print_html(html)
    file.close()
    if not html.split('\n') == phtml.split('\n'):
        temp_file = open('/var/tmp/pretty_html.txt', 'w')
        temp_file.write(phtml)
        temp_file.close()
        print('Invalid Indentation detected in file: '
              '%s\nDiff for the file against expected indented file:' % (fn))
        subprocess.call(['diff', fn, '/var/tmp/pretty_html.txt'], stderr=subprocess.STDOUT)
        return 0
    return 1
