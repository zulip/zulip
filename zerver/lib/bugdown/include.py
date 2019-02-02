from __future__ import print_function
import re
import os
from typing import Any, Dict, List

import markdown
from markdown_include.include import MarkdownInclude, IncludePreprocessor

from zerver.lib.exceptions import InvalidMarkdownIncludeStatement

INC_SYNTAX = re.compile(r'\{!\s*(.+?)\s*!\}')


class MarkdownIncludeCustom(MarkdownInclude):
    def extendMarkdown(self, md: markdown.Markdown, md_globals: Dict[str, Any]) -> None:
        md.preprocessors.add(
            'include_wrapper',
            IncludeCustomPreprocessor(md, self.getConfigs()),
            '_begin'
        )

class IncludeCustomPreprocessor(IncludePreprocessor):
    """
    This is a custom implementation of the markdown_include
    extension that checks for include statements and if the included
    macro file does not exist or can't be opened, raises a custom
    JsonableError exception. The rest of the functionality is identical
    to the original markdown_include extension.
    """
    def run(self, lines: List[str]) -> List[str]:
        done = False
        while not done:
            for line in lines:
                loc = lines.index(line)
                m = INC_SYNTAX.search(line)

                if m:
                    filename = m.group(1)
                    filename = os.path.expanduser(filename)
                    if not os.path.isabs(filename):
                        filename = os.path.normpath(
                            os.path.join(self.base_path, filename)
                        )
                    try:
                        with open(filename, 'r', encoding=self.encoding) as r:
                            text = r.readlines()
                    except Exception as e:
                        print('Warning: could not find file {}. Error: {}'.format(filename, e))
                        lines[loc] = INC_SYNTAX.sub('', line)
                        raise InvalidMarkdownIncludeStatement(m.group(0).strip())

                    line_split = INC_SYNTAX.split(line)
                    if len(text) == 0:
                        text.append('')
                    for i in range(len(text)):
                        text[i] = text[i].rstrip('\r\n')
                    text[0] = line_split[0] + text[0]
                    text[-1] = text[-1] + line_split[2]
                    lines = lines[:loc] + text + lines[loc+1:]
                    break
            else:
                done = True

        return lines

def makeExtension(*args: Any, **kwargs: str) -> MarkdownIncludeCustom:
    return MarkdownIncludeCustom(kwargs)
