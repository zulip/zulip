import re
import os
import sys
import ujson
import inspect

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from typing import Any, Dict, Optional, List
import markdown

ZULIP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TOOLS_DIR = os.path.join(ZULIP_DIR, 'tools', 'lib')
sys.path.insert(0, TOOLS_DIR)

import api_tests

REGEXP = re.compile(r'\{generate_code_example\|\s*(.+?)\s*\|\s*(.+?)\s*\}')

PYTHON_CLIENT_CONFIG_LINES = """
#!/usr/bin/env python3

import zulip

# Download ~/zuliprc-dev from your dev server
client = zulip.Client(config_file="~/zuliprc-dev")

"""


class APICodeExamplesGenerator(Extension):
    def extendMarkdown(self, md: markdown.Markdown, md_globals: Dict[str, Any]) -> None:
        md.preprocessors.add(
            'generate_code_example', APICodeExamplesPreprocessor(md, self.getConfigs()), '_begin'
        )


class APICodeExamplesPreprocessor(Preprocessor):
    def __init__(self, md: markdown.Markdown, config: Dict[str, Any]) -> None:
        super(APICodeExamplesPreprocessor, self).__init__(md)

    def run(self, lines: List[str]) -> List[str]:
        done = False
        while not done:
            for line in lines:
                loc = lines.index(line)
                match = REGEXP.search(line)

                if match:
                    function = match.group(1)
                    key = match.group(2)

                    if key == 'fixture':
                        text = self.render_fixture(function)
                    elif key == 'method':
                        text = self.render_code_example(function)

                    # The line that contains the directive to include the macro
                    # may be preceded or followed by text or tags, in that case
                    # we need to make sure that any preceding or following text
                    # stays the same.
                    line_split = REGEXP.split(line, maxsplit=0)
                    preceding = line_split[0]
                    following = line_split[-1]
                    text = [preceding] + text + [following]
                    lines = lines[:loc] + text + lines[loc+1:]
                    break
            else:
                done = True
        return lines

    def render_fixture(self, function: str) -> List[str]:
        fixture = []

        fixture_dict = api_tests.FIXTURES[function]
        fixture_json = ujson.dumps(fixture_dict, indent=4, sort_keys=True)

        fixture.append('```')
        fixture.extend(fixture_json.splitlines())
        fixture.append('```')

        return fixture

    def render_code_example(self, function: str) -> List[str]:
        method = api_tests.TEST_FUNCTIONS[function]
        function_source_lines = inspect.getsourcelines(method)[0]
        ce_regex = re.compile(r'\# \{code_example\|\s*(.+?)\s*\}')

        start = 0
        end = 0
        for line in function_source_lines:
            match = ce_regex.search(line)
            if match:
                if match.group(1) == 'start':
                    start = function_source_lines.index(line)
                elif match.group(1) == 'end':
                    end = function_source_lines.index(line)

        config = PYTHON_CLIENT_CONFIG_LINES.splitlines()
        snippet = function_source_lines[start + 1: end]

        code_example = []
        code_example.append('```')
        code_example.extend(config)

        for line in snippet:
            # Remove one level of indentation and strip newlines
            code_example.append(line[4:].rstrip())

        code_example.append('print(result)')
        code_example.append('```')

        return code_example

def makeExtension(*args: Any, **kwargs: str) -> APICodeExamplesGenerator:
    return APICodeExamplesGenerator(kwargs)
